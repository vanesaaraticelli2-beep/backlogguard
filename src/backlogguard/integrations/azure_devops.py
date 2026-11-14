"""Adaptador server-side para Azure DevOps Work Item Tracking REST API 7.1."""
from __future__ import annotations

import base64
import json
import re
import socket
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from backlogguard.integrations.gateway import (
    BacklogAuthenticationError,
    BacklogError,
    BacklogNotFoundError,
    BacklogPermissionError,
    BacklogRateLimitError,
    BacklogTimeout,
    ConflictError,
    WorkItem,
)
from backlogguard.llm.settings import Settings

API_VERSION = "7.1"
MAX_WIQL_ITEMS = 2000
BATCH_SIZE = 200


class AzureDevOpsBacklog:
    """Implementación Azure de `BacklogGateway`; la construcción no realiza llamadas de red."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: Callable[[Request, float], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if settings.app_env != "development":
            raise BacklogError("El PAT de AZDO_MODE=real solo se admite en app_env=development.")
        org_url = settings.azdo_org_url.strip().rstrip("/")
        parsed = urlsplit(org_url)
        if (
            parsed.scheme != "https"
            or not parsed.netloc
            or parsed.path not in ("", "/")
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise BacklogError("AZDO_ORG_URL debe ser una URL HTTPS válida de la organización, sin credenciales ni parámetros.")
        host = (parsed.hostname or "").casefold()
        if host != "dev.azure.com" and not host.endswith(".visualstudio.com"):
            raise BacklogError("AZDO_ORG_URL debe pertenecer a dev.azure.com o a una organización visualstudio.com.")
        token = settings.azdo_token_value()
        if not token:
            raise BacklogError("AZDO_TOKEN es obligatorio para la conexión real.")
        self.organization_url = org_url
        self.project = settings.azdo_project.strip()
        self._token = token
        self._timeout = settings.request_timeout_seconds
        self._max_retries = settings.max_retries
        self._retry_base_delay = settings.retry_base_delay_seconds
        self._transport = transport or _open_url
        self._sleep = sleep
        self._type_overrides = {
            "Epic": settings.azdo_epic_type,
            "User Story": settings.azdo_story_type,
            "Task": settings.azdo_task_type,
        }
        self._type_names: list[str] | None = None
        self._field_cache: dict[str, set[str]] = {}

    def _project_api(self, path: str) -> str:
        project = quote(self.project, safe="")
        return f"{project}/_apis/{path.lstrip('/')}"

    def _organization_api(self, path: str) -> str:
        return f"_apis/{path.lstrip('/')}"

    def _url(self, path: str, query: dict[str, str] | None = None) -> str:
        params = {"api-version": API_VERSION, **(query or {})}
        return f"{self.organization_url}/{path}?{urlencode(params)}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, str] | None = None,
        payload: Any = None,
        patch: bool = False,
        retryable: bool = False,
    ) -> dict[str, Any]:
        url = self._url(path, query)
        headers = {
            "Authorization": "Basic " + base64.b64encode(f":{self._token}".encode("utf-8")).decode("ascii"),
            "Accept": "application/json",
        }
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json-patch+json" if patch else "application/json"
        request = Request(url, data=body, headers=headers, method=method)
        retries = self._max_retries if retryable else 0

        for attempt in range(retries + 1):
            try:
                response = self._transport(request, self._timeout)
                try:
                    raw = response.read()
                finally:
                    close = getattr(response, "close", None)
                    if close:
                        close()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
            except HTTPError as exc:
                detail = self._safe_detail(exc.read().decode("utf-8", errors="replace"))
                if retryable and exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                    self._sleep(self._retry_delay(attempt, exc.headers.get("Retry-After")))
                    continue
                message = f"Azure DevOps respondió HTTP {exc.code}"
                if detail:
                    message += f": {detail}"
                if exc.code == 401:
                    raise BacklogAuthenticationError("Credenciales de Azure DevOps inválidas o vencidas.") from exc
                if exc.code == 403:
                    raise BacklogPermissionError("Azure DevOps rechazó la operación por falta de permisos.") from exc
                if exc.code == 404:
                    raise BacklogNotFoundError(message) from exc
                if exc.code in (409, 412):
                    raise ConflictError(message) from exc
                if exc.code == 429:
                    raise BacklogRateLimitError(message) from exc
                raise BacklogError(message) from exc
            except (TimeoutError, socket.timeout) as exc:
                if retryable and attempt < retries:
                    self._sleep(self._retry_delay(attempt))
                    continue
                raise BacklogTimeout("Tiempo de espera agotado al comunicarse con Azure DevOps.") from exc
            except URLError as exc:
                if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                    if retryable and attempt < retries:
                        self._sleep(self._retry_delay(attempt))
                        continue
                    raise BacklogTimeout("Tiempo de espera agotado al comunicarse con Azure DevOps.") from exc
                raise BacklogError("No se pudo establecer conexión con Azure DevOps.") from exc
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise BacklogError("Azure DevOps devolvió una respuesta JSON inválida.") from exc
        raise BacklogError("La solicitud a Azure DevOps agotó los reintentos.")  # pragma: no cover

    def _retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        if retry_after:
            try:
                return min(max(float(retry_after), 0.0), 3.0)
            except ValueError:
                pass
        return min(self._retry_base_delay * (2**attempt), 3.0)

    def _safe_detail(self, detail: str) -> str:
        return detail.replace(self._token, "[REDACTED]")[:500].strip()

    def list_projects(self) -> list[dict[str, str]]:
        """Devuelve los proyectos que la identidad autenticada puede consultar."""
        response = self._request(
            "GET",
            self._organization_api("projects"),
            query={"stateFilter": "wellFormed", "$top": "1000"},
            retryable=True,
        )
        return [
            {"id": str(project.get("id", "")), "name": str(project.get("name", ""))}
            for project in response.get("value", [])
        ]

    def list_work_item_types(self) -> list[str]:
        response = self._request(
            "GET",
            self._project_api("wit/workitemtypes"),
            retryable=True,
        )
        self._type_names = [str(item["name"]) for item in response.get("value", []) if item.get("name")]
        return list(self._type_names)

    def test_connection(self) -> dict[str, Any]:
        """Valida acceso a la organización/proyecto y descubre los tipos del proceso configurado."""
        project = self._request(
            "GET",
            self._organization_api(f"projects/{quote(self.project, safe='')}"),
            retryable=True,
        )
        types = self.list_work_item_types()
        return {
            "organization_url": self.organization_url,
            "project": str(project.get("name", self.project)),
            "work_item_types": types,
        }

    def resolve_work_item_type(self, requested_type: str) -> str:
        if self._type_names is None:
            self.list_work_item_types()
        assert self._type_names is not None
        override = self._type_overrides.get(requested_type)
        candidates = [override] if override else {
            "Epic": ["Epic"],
            "User Story": ["User Story", "Product Backlog Item"],
            "Task": ["Task"],
        }.get(requested_type, [requested_type])
        selected = next((name for name in candidates if name in self._type_names), None)
        if selected is None:
            available = ", ".join(self._type_names) or "(ninguno)"
            raise BacklogError(
                f"El proyecto {self.project} no tiene un tipo compatible con {requested_type!r}. "
                f"Tipos disponibles: {available}. Configurá AZDO_*_TYPE si corresponde."
            )
        return selected

    def list_work_item_states(self, work_item_type: str) -> list[dict[str, str]]:
        """Return the process-defined states and categories for a work item type."""
        response = self._request(
            "GET",
            self._project_api(f"wit/workitemtypes/{quote(work_item_type, safe='')}/states"),
            retryable=True,
        )
        return [
            {"name": str(item["name"]), "category": str(item.get("stateCategory", ""))}
            for item in response.get("value", [])
            if isinstance(item, dict) and item.get("name")
        ]

    def _field_references(self, work_item_type: str) -> set[str]:
        if work_item_type not in self._field_cache:
            result = self._request(
                "GET",
                self._project_api(f"wit/workitemtypes/{quote(work_item_type, safe='')}"),
                query={"$expand": "Fields"},
                retryable=True,
            )
            fields = result.get("fields", [])
            references = {
                str(field["referenceName"])
                for field in fields
                if isinstance(field, dict) and field.get("referenceName")
            }
            if "System.Title" not in references:
                raise BacklogError(f"El tipo {work_item_type!r} no expone el campo obligatorio System.Title.")
            self._field_cache[work_item_type] = references
        return self._field_cache[work_item_type]

    def _work_item_url(self, work_item_id: int) -> str:
        return f"{self.organization_url}/{quote(self.project, safe='')}/_workitems/edit/{work_item_id}"

    def _item_api(self, work_item_id: int) -> str:
        return self._project_api(f"wit/workitems/{work_item_id}")

    def _raw_item(self, work_item_id: int) -> dict[str, Any]:
        return self._request(
            "GET",
            self._item_api(work_item_id),
            query={"$expand": "Relations"},
            retryable=True,
        )

    def _parse_item(self, raw: dict[str, Any]) -> WorkItem:
        fields = raw.get("fields", {})
        project = str(fields.get("System.TeamProject", self.project))
        if project.casefold() != self.project.casefold():
            raise BacklogError(f"El work item #{raw.get('id')} no pertenece al proyecto {self.project}.")
        relations = raw.get("relations", [])
        parent_id = None
        for relation in relations:
            if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse":
                found = re.search(r"/workitems?/(\d+)(?:$|[?#])", str(relation.get("url", "")), re.IGNORECASE)
                if found:
                    parent_id = int(found.group(1))
                    break
        raw_tags = fields.get("System.Tags", "")
        tags = [tag.strip() for tag in raw_tags.split(";") if tag.strip()] if isinstance(raw_tags, str) else []
        criteria = fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
        if isinstance(criteria, list):
            acceptance_criteria = [str(value) for value in criteria]
        else:
            acceptance_criteria = [str(criteria)] if criteria else []
        return WorkItem(
            id=int(raw["id"]),
            type=str(fields.get("System.WorkItemType", "")),
            title=str(fields.get("System.Title") or ""),
            description=str(fields.get("System.Description") or ""),
            acceptance_criteria=acceptance_criteria,
            tags=tags,
            parent_id=parent_id,
            rev=int(raw.get("rev", 1)),
            state=str(fields.get("System.State", "New")),
            url=self._work_item_url(int(raw["id"])),
        )

    def _validate_project_item(self, work_item_id: int) -> dict[str, Any]:
        raw = self._raw_item(work_item_id)
        project = str(raw.get("fields", {}).get("System.TeamProject", ""))
        if project.casefold() != self.project.casefold():
            raise BacklogError(f"El work item #{work_item_id} no pertenece al proyecto {self.project}.")
        return raw

    def get(self, work_item_id: int) -> WorkItem | None:
        try:
            return self._parse_item(self._validate_project_item(work_item_id))
        except BacklogNotFoundError:
            return None

    def get_children(self, work_item_id: int) -> list[WorkItem]:
        if self.get(work_item_id) is None:
            return []
        project_literal = "'" + self.project.replace("'", "''") + "'"
        wiql = (
            "SELECT [System.Id] FROM WorkItems WHERE "
            f"[System.TeamProject] = {project_literal} AND "
            f"[System.Parent] = {work_item_id} ORDER BY [System.Id]"
        )
        result = self._request(
            "POST",
            self._project_api("wit/wiql"),
            query={"$top": str(MAX_WIQL_ITEMS)},
            payload={"query": wiql},
            retryable=True,
        )
        item_ids = [
            int(item["id"])
            for item in result.get("workItems", [])
            if item.get("id") is not None
        ]
        if len(item_ids) >= MAX_WIQL_ITEMS:
            raise BacklogError(
                f"La consulta de hijos superó el límite de {MAX_WIQL_ITEMS} work items."
            )
        return self._get_many(item_ids)

    def _query_work_item_ids(self, text: str | None, tag: str | None) -> list[int]:
        def wiql_literal(value: str) -> str:
            return "'" + value.replace("'", "''") + "'"

        conditions = [f"[System.TeamProject] = {wiql_literal(self.project)}"]
        if text:
            conditions.append(f"[System.Title] CONTAINS {wiql_literal(text)}")
        if tag:
            conditions.append(f"[System.Tags] CONTAINS {wiql_literal(tag)}")
        wiql = "SELECT [System.Id] FROM WorkItems WHERE " + " AND ".join(conditions) + " ORDER BY [System.Id]"
        result = self._request(
            "POST",
            self._project_api("wit/wiql"),
            query={"$top": str(MAX_WIQL_ITEMS)},
            payload={"query": wiql},
            retryable=True,
        )
        item_ids = [int(item["id"]) for item in result.get("workItems", []) if item.get("id") is not None]
        if len(item_ids) >= MAX_WIQL_ITEMS:
            raise BacklogError(
                f"La búsqueda superó el límite de {MAX_WIQL_ITEMS} work items; acotá la consulta para evitar omitir duplicados."
            )
        return item_ids

    def _get_many(self, work_item_ids: list[int]) -> list[WorkItem]:
        items: list[WorkItem] = []
        for offset in range(0, len(work_item_ids), BATCH_SIZE):
            chunk = work_item_ids[offset : offset + BATCH_SIZE]
            result = self._request(
                "GET",
                self._project_api("wit/workitems"),
                query={"ids": ",".join(str(item_id) for item_id in chunk), "$expand": "Relations"},
                retryable=True,
            )
            items.extend(self._parse_item(item) for item in result.get("value", []))
        return sorted(items, key=lambda item: item.id)

    def search(self, *, text: str | None = None, tag: str | None = None) -> list[WorkItem]:
        items = self._get_many(self._query_work_item_ids(text, tag))
        if tag is not None:
            items = [item for item in items if tag in item.tags]
        if text:
            needle = text.casefold()
            items = [item for item in items if needle in item.title.casefold()]
        return items

    def reload(self) -> None:
        """Invalida metadata local; los work items se consultan frescos en cada operación."""
        self._type_names = None
        self._field_cache.clear()

    def _field_patch(self, work_item_type: str, *, title: str, description: str, acceptance_criteria: list[str], tags: list[str]) -> list[dict[str, Any]]:
        available = self._field_references(work_item_type)
        patch: list[dict[str, Any]] = [
            {"op": "add", "path": "/fields/System.Title", "value": title},
        ]
        values = {
            "System.Description": description,
            "Microsoft.VSTS.Common.AcceptanceCriteria": "\n".join(acceptance_criteria),
            "System.Tags": "; ".join(tags),
        }
        for reference, value in values.items():
            if reference in available:
                patch.append({"op": "add", "path": f"/fields/{reference}", "value": value})
        return patch

    def _parent_relation(self, parent_id: int) -> dict[str, Any]:
        self._validate_project_item(parent_id)
        return {
            "rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": f"{self.organization_url}/{quote(self.project, safe='')}/_apis/wit/workItems/{parent_id}",
        }

    def create(
        self,
        *,
        type: str,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
        parent_id: int | None,
    ) -> WorkItem:
        actual_type = self.resolve_work_item_type(type)
        patch = self._field_patch(
            actual_type,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            tags=tags,
        )
        if parent_id is not None:
            patch.append({"op": "add", "path": "/relations/-", "value": self._parent_relation(parent_id)})
        response = self._request(
            "POST",
            self._project_api(f"wit/workitems/${quote(actual_type, safe='')}"),
            query={"$validateOnly": "false"},
            payload=patch,
            patch=True,
        )
        response.setdefault("fields", {}).setdefault("System.TeamProject", self.project)
        return self._parse_item(response)

    def update(
        self,
        work_item_id: int,
        *,
        expected_rev: int,
        title: str,
        description: str,
        acceptance_criteria: list[str],
        tags: list[str],
    ) -> WorkItem:
        current = self._validate_project_item(work_item_id)
        if int(current.get("rev", 1)) != expected_rev:
            raise ConflictError(f"#{work_item_id}: versión {current.get('rev')}, se esperaba {expected_rev}")
        work_item_type = str(current.get("fields", {}).get("System.WorkItemType", ""))
        patch = [{"op": "test", "path": "/rev", "value": expected_rev}]
        patch.extend(self._field_patch(
            work_item_type,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            tags=tags,
        ))
        response = self._request(
            "PATCH",
            self._item_api(work_item_id),
            payload=patch,
            patch=True,
        )
        return self._parse_item(response)

    def link_parent(self, work_item_id: int, parent_id: int, *, expected_rev: int) -> WorkItem:
        child = self._validate_project_item(work_item_id)
        if int(child.get("rev", 1)) != expected_rev:
            raise ConflictError(f"#{work_item_id}: versión {child.get('rev')}, se esperaba {expected_rev}")
        current = self._parse_item(child)
        if current.parent_id == parent_id:
            return current
        parent_relation_index = next(
            (
                index
                for index, relation in enumerate(child.get("relations", []))
                if relation.get("rel") == "System.LinkTypes.Hierarchy-Reverse"
            ),
            None,
        )
        relation_operation = (
            {"op": "replace", "path": f"/relations/{parent_relation_index}", "value": self._parent_relation(parent_id)}
            if parent_relation_index is not None
            else {"op": "add", "path": "/relations/-", "value": self._parent_relation(parent_id)}
        )
        patch = [
            {"op": "test", "path": "/rev", "value": expected_rev},
            relation_operation,
        ]
        response = self._request("PATCH", self._item_api(work_item_id), payload=patch, patch=True)
        return self._parse_item(response)

    def transition_state(
        self, work_item_id: int, *, expected_rev: int, state: str
    ) -> WorkItem:
        """Move a work item to one of the states supported by its configured process."""
        current = self._validate_project_item(work_item_id)
        if int(current.get("rev", 1)) != expected_rev:
            raise ConflictError(
                f"#{work_item_id}: versión {current.get('rev')}, se esperaba {expected_rev}"
            )
        work_item_type = str(current.get("fields", {}).get("System.WorkItemType", ""))
        states = self.list_work_item_states(work_item_type)
        if state not in {item["name"] for item in states}:
            raise BacklogError(
                f"El estado {state!r} no está disponible para {work_item_type!r}."
            )
        if str(current.get("fields", {}).get("System.State", "")) == state:
            return self._parse_item(current)
        response = self._request(
            "PATCH",
            self._item_api(work_item_id),
            payload=[
                {"op": "test", "path": "/rev", "value": expected_rev},
                {"op": "add", "path": "/fields/System.State", "value": state},
            ],
            patch=True,
        )
        return self._parse_item(response)


def _open_url(request: Request, timeout: float) -> Any:
    return urlopen(request, timeout=timeout)
