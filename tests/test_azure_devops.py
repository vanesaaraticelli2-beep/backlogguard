import base64
import io
from email.message import Message
from urllib.error import HTTPError
from urllib.parse import unquote

import pytest

from backlogguard.integrations import (
    AzureDevOpsBacklog,
    BacklogAuthenticationError,
    BacklogError,
    BacklogPermissionError,
    BacklogRateLimitError,
    BacklogTimeout,
    MCPBacklog,
    build_backlog,
)
from backlogguard.llm import Settings

ORG = "https://tp-itba.visualstudio.com"
PROJECT = "TP-ITBA"
PAT = "pat-de-prueba"


class Response:
    def __init__(self, value):
        import json

        self.data = json.dumps(value).encode("utf-8")

    def read(self):
        return self.data

    def close(self):
        pass


def settings(**overrides):
    values = dict(
        azdo_mode="real",
        azdo_org_url=ORG,
        azdo_project=PROJECT,
        azdo_token=PAT,
        max_retries=0,
        retry_base_delay_seconds=0,
    )
    values.update(overrides)
    return Settings(**values)


def item_response(work_item_id=101, *, item_type="Product Backlog Item", parent_id=None):
    relations = []
    if parent_id:
        relations.append({
            "rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": f"{ORG}/{PROJECT}/_apis/wit/workItems/{parent_id}",
        })
    return {
        "id": work_item_id,
        "rev": 3,
        "fields": {
            "System.TeamProject": PROJECT,
            "System.WorkItemType": item_type,
            "System.Title": "Historia de prueba",
            "System.Description": "Descripción",
            "System.State": "New",
            "System.Tags": "bg-item:HU-1; bg-key:abc",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "Dado un caso",
        },
        "relations": relations,
        "_links": {"html": {"href": f"{ORG}/{PROJECT}/_workitems/edit/{work_item_id}"}},
    }


class CreateTransport:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        url = unquote(request.full_url)
        if "wit/workitemtypes?" in url:
            return Response({"value": [{"name": "Epic"}, {"name": "Product Backlog Item"}, {"name": "Task"}]})
        if "wit/workitemtypes/Product Backlog Item?" in url:
            refs = [
                "System.Title",
                "System.Description",
                "System.Tags",
                "Microsoft.VSTS.Common.AcceptanceCriteria",
            ]
            return Response({"fields": [{"referenceName": ref} for ref in refs]})
        if "wit/workitems/99?" in url:
            return Response(item_response(99, item_type="Epic"))
        if request.get_method() == "POST" and "wit/workitems/$Product Backlog Item?" in url:
            return Response(item_response(parent_id=99))
        raise AssertionError(f"Unexpected test request: {request.get_method()} {request.full_url}")


def test_real_mode_exige_configuracion_y_restringe_pat_a_desarrollo():
    with pytest.raises(BacklogError, match="AZDO_TOKEN"):
        build_backlog(Settings(azdo_mode="real", azdo_org_url=ORG))
    with pytest.raises(BacklogError, match="development"):
        build_backlog(settings(app_env="production"))
    with pytest.raises(BacklogError, match="development"):
        AzureDevOpsBacklog(settings(app_env="production"))
    with pytest.raises(BacklogError, match="HTTPS"):
        AzureDevOpsBacklog(settings(azdo_org_url="http://tp-itba.visualstudio.com"))
    with pytest.raises(BacklogError, match="visualstudio.com"):
        AzureDevOpsBacklog(settings(azdo_org_url="https://attacker.example"))
    rest_backlog = AzureDevOpsBacklog(settings())
    backlog = build_backlog(settings())
    assert isinstance(backlog, MCPBacklog) and rest_backlog._type_names is None


def test_settings_no_expone_pat_en_repr_ni_safe_dict():
    configured = settings()
    assert PAT not in repr(configured)
    assert PAT not in str(configured.safe_dict())
    assert configured.safe_dict()["azdo_token"] == "***configurado***"


def test_scrum_mapea_user_story_a_product_backlog_item_y_crea_json_patch_con_padre():
    transport = CreateTransport()
    backlog = AzureDevOpsBacklog(settings(), transport=transport)

    created = backlog.create(
        type="User Story",
        title="Historia de prueba",
        description="Descripción",
        acceptance_criteria=["Dado un caso"],
        tags=["bg-item:HU-1", "bg-key:abc"],
        parent_id=99,
    )

    assert created.id == 101
    assert created.type == "Product Backlog Item"
    assert created.parent_id == 99
    assert created.url == f"{ORG}/{PROJECT}/_workitems/edit/101"
    create_request = transport.requests[-1]
    assert create_request.get_method() == "POST"
    assert create_request.get_header("Content-type") == "application/json-patch+json"
    auth = create_request.get_header("Authorization")
    assert base64.b64decode(auth.removeprefix("Basic ")).decode("utf-8") == f":{PAT}"
    import json

    patch = json.loads(create_request.data)
    values = {operation["path"]: operation.get("value") for operation in patch}
    assert values["/fields/System.Title"] == "Historia de prueba"
    assert values["/fields/Microsoft.VSTS.Common.AcceptanceCriteria"] == "Dado un caso"
    assert values["/relations/-"]["rel"] == "System.LinkTypes.Hierarchy-Reverse"


def test_search_usa_wiql_del_proyecto_y_devuelve_id_estado_relacion_y_url():
    seen = []

    def transport(request, timeout):
        seen.append(request)
        if "wit/wiql?" in request.full_url:
            return Response({"workItems": [{"id": 101}]})
        if "wit/workitems?" in request.full_url:
            return Response({"value": [item_response(parent_id=99)]})
        raise AssertionError(request.full_url)

    backlog = AzureDevOpsBacklog(settings(), transport=transport)
    (item,) = backlog.search(text="Historia", tag="bg-key:abc")

    assert item.id == 101 and item.parent_id == 99 and item.state == "New"
    assert item.url == f"{ORG}/{PROJECT}/_workitems/edit/101"
    assert "[System.TeamProject] = 'TP-ITBA'" in seen[0].data.decode("utf-8")
    assert "[System.Title] CONTAINS 'Historia'" in seen[0].data.decode("utf-8")
    assert "[System.Tags] CONTAINS 'bg-key:abc'" in seen[0].data.decode("utf-8")


def test_test_connection_y_list_projects_descubren_proyecto_y_tipos_sin_escrituras():
    seen = []

    def transport(request, timeout):
        seen.append(request)
        if "/_apis/projects/TP-ITBA?" in request.full_url:
            return Response({"name": PROJECT})
        if "wit/workitemtypes?" in request.full_url:
            return Response({"value": [{"name": "Epic"}, {"name": "Product Backlog Item"}, {"name": "Task"}]})
        if "/_apis/projects?" in request.full_url:
            return Response({"value": [{"id": "p1", "name": PROJECT}, {"id": "p2", "name": "Sandbox"}]})
        raise AssertionError(request.full_url)

    backlog = AzureDevOpsBacklog(settings(), transport=transport)
    assert backlog.test_connection() == {
        "organization_url": ORG,
        "project": PROJECT,
        "work_item_types": ["Epic", "Product Backlog Item", "Task"],
    }
    assert backlog.list_projects() == [{"id": "p1", "name": PROJECT}, {"id": "p2", "name": "Sandbox"}]
    assert all(request.get_method() == "GET" for request in seen)


def test_descubre_estados_del_proceso_y_cambia_estado_con_revision_esperada():
    seen = []

    def transport(request, timeout):
        seen.append(request)
        url = unquote(request.full_url)
        if "wit/workitemtypes/Product Backlog Item/states?" in url:
            return Response(
                {
                    "value": [
                        {"name": "New", "stateCategory": "Proposed"},
                        {"name": "Removed", "stateCategory": "Removed"},
                    ]
                }
            )
        if request.get_method() == "PATCH":
            response = item_response(101, item_type="Product Backlog Item")
            response["rev"] = 4
            response["fields"]["System.State"] = "Removed"
            return Response(response)
        if "wit/workitems/101?" in url:
            return Response(item_response(101, item_type="Product Backlog Item"))
        raise AssertionError(request.full_url)

    backlog = AzureDevOpsBacklog(settings(), transport=transport)

    assert backlog.list_work_item_states("Product Backlog Item") == [
        {"name": "New", "category": "Proposed"},
        {"name": "Removed", "category": "Removed"},
    ]
    retired = backlog.transition_state(101, expected_rev=3, state="Removed")

    assert retired.state == "Removed" and retired.rev == 4
    patch = next(request for request in seen if request.get_method() == "PATCH")
    operations = __import__("json").loads(patch.data.decode("utf-8"))
    assert operations[0] == {"op": "test", "path": "/rev", "value": 3}
    assert operations[1]["path"] == "/fields/System.State"
    assert operations[1]["value"] == "Removed"


def test_rechaza_estado_que_no_pertenece_al_proceso_antes_de_escribir():
    writes = []

    def transport(request, timeout):
        url = unquote(request.full_url)
        if "wit/workitemtypes/Product Backlog Item/states?" in url:
            return Response({"value": [{"name": "New", "stateCategory": "Proposed"}]})
        if request.get_method() == "PATCH":
            writes.append(request)
        if "wit/workitems/101?" in url:
            return Response(item_response(101, item_type="Product Backlog Item"))
        raise AssertionError(request.full_url)

    backlog = AzureDevOpsBacklog(settings(), transport=transport)
    with pytest.raises(BacklogError, match="no está disponible"):
        backlog.transition_state(101, expected_rev=3, state="Removed")

    assert writes == []


def test_consulta_hijos_directos_por_parent_id_en_el_proyecto():
    seen = []

    def transport(request, timeout):
        seen.append(request)
        url = unquote(request.full_url)
        if request.get_method() == "POST" and "wit/wiql?" in url:
            return Response({"workItems": [{"id": 102}]})
        if "wit/workitems/101?" in url:
            return Response(item_response(101, item_type="Product Backlog Item"))
        if "wit/workitems/102?" in url:
            return Response(item_response(102, item_type="Task", parent_id=101))
        if "wit/workitems?" in url:
            return Response({"value": [item_response(102, item_type="Task", parent_id=101)]})
        raise AssertionError(request.full_url)

    children = AzureDevOpsBacklog(settings(), transport=transport).get_children(101)

    assert [child.id for child in children] == [102]
    query = next(request for request in seen if request.get_method() == "POST")
    assert "[System.Parent] = 101" in query.data.decode("utf-8")


def test_transporte_real_pasa_timeout_como_keyword(monkeypatch):
    import backlogguard.integrations.azure_devops as azure_module

    calls = []

    def fake_urlopen(request, *, timeout):
        calls.append((request, timeout))
        return Response({"value": [{"name": "Epic"}]})

    monkeypatch.setattr(azure_module, "urlopen", fake_urlopen)
    backlog = AzureDevOpsBacklog(settings(request_timeout_seconds=7.5))

    assert backlog.list_work_item_types() == ["Epic"]
    assert calls[0][1] == 7.5


def test_no_vincula_work_item_de_otro_proyecto():
    transport = CreateTransport()

    def wrong_parent(request, timeout):
        if "wit/workitems/99?" in unquote(request.full_url):
            response = item_response(99, item_type="Epic")
            response["fields"]["System.TeamProject"] = "OtroProyecto"
            return Response(response)
        return transport(request, timeout)

    backlog = AzureDevOpsBacklog(settings(), transport=wrong_parent)
    with pytest.raises(BacklogError, match="no pertenece"):
        backlog.create(
            type="User Story",
            title="Historia",
            description="",
            acceptance_criteria=[],
            tags=[],
            parent_id=99,
        )
    assert not any(request.get_method() == "POST" for request in transport.requests)


def test_reemplaza_el_padre_existente_sin_agregar_una_relacion_duplicada():
    seen = []

    def transport(request, timeout):
        seen.append(request)
        url = unquote(request.full_url)
        if request.get_method() == "PATCH":
            return Response(item_response(101, parent_id=99))
        if "wit/workitems/101?" in url:
            return Response(item_response(101, parent_id=98))
        if "wit/workitems/99?" in url:
            return Response(item_response(99, item_type="Epic"))
        raise AssertionError(request.full_url)

    backlog = AzureDevOpsBacklog(settings(), transport=transport)
    linked = backlog.link_parent(101, 99, expected_rev=3)

    assert linked.parent_id == 99
    import json

    patch = json.loads(seen[-1].data)
    assert patch[0] == {"op": "test", "path": "/rev", "value": 3}
    assert patch[1]["op"] == "replace" and patch[1]["path"] == "/relations/0"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, BacklogAuthenticationError),
        (403, BacklogPermissionError),
        (429, BacklogRateLimitError),
    ],
)
def test_traduce_errores_http_sin_revelar_pat(status, error):
    def reject(request, timeout):
        headers = Message()
        raise HTTPError(request.full_url, status, "falló", headers, io.BytesIO(PAT.encode()))

    backlog = AzureDevOpsBacklog(settings(), transport=reject)
    with pytest.raises(error) as caught:
        backlog.list_work_item_types()
    assert PAT not in str(caught.value)


def test_reintenta_solo_lecturas_transitorias_y_expone_timeout():
    calls = []

    def rate_limit_once(request, timeout):
        calls.append(request)
        if len(calls) == 1:
            headers = Message()
            headers["Retry-After"] = "0"
            raise HTTPError(request.full_url, 429, "rate limited", headers, io.BytesIO(b""))
        return Response({"value": [{"name": "Epic"}]})

    backlog = AzureDevOpsBacklog(settings(max_retries=1), transport=rate_limit_once, sleep=lambda _: None)
    assert backlog.list_work_item_types() == ["Epic"]
    assert len(calls) == 2

    def timeout(request, timeout):
        raise TimeoutError

    with pytest.raises(BacklogTimeout):
        AzureDevOpsBacklog(settings(), transport=timeout).list_work_item_types()
