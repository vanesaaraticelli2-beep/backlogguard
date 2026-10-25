# Arquitectura implementada: flujo de Requerimientos

Estos diagramas describen el código que existe hoy, no una arquitectura objetivo.
El flujo integrado corresponde a `build_graph` → `plan` → `produce`; el script
`scripts/run_requerimientos.py` también permite ejecutar el productor directamente,
sin Supervisor ni grafo.

## 1. Secuencia de llamadas reales

La secuencia muestra el flujo de producción dentro del pipeline. Las llamadas al
LLM ocurren en `LLMDecider` mediante el proveedor configurado. El modelo devuelve
una decisión JSON validada; no se usa function calling nativo para este ciclo.

```mermaid
sequenceDiagram
    actor Operador
    participant Graph as build_graph / LangGraph
    participant Deps as index_library
    participant Supervisor as plan_run (Supervisor)
    participant SupervisorLoop as run_basic_agent
    participant SupervisorLLM as LLMDecider + provider
    participant SupervisorRegistry as ToolRegistry Supervisor
    participant Produce as nodo produce
    participant Requirements as run_requerimientos
    participant ReqLoop as run_basic_agent
    participant ReqLLM as LLMDecider + provider
    participant ReqRegistry as ToolRegistry Requerimientos
    participant Toolkit as RequirementsToolkit
    participant Library as SourceLibrary
    participant Retriever as Retriever
    participant Board as Board

    Operador->>Graph: build_graph(deps, checkpointer)
    Note over Graph,Deps: build_graph indexa todas las fuentes una vez al compilar
    Graph->>Deps: index_library(library, retriever)
    Deps->>Library: describe() / load(document_id)
    Deps->>Retriever: index(build_chunks(...))
    Graph-->>Operador: grafo compilado
    Operador->>Graph: run_pipeline(objective, thread_id)

    Graph->>Supervisor: plan_run(objective, library, policy)
    Supervisor->>SupervisorLoop: run_basic_agent(objective + catálogo)
    Note over Supervisor,SupervisorLoop: usa su propio registry y sus tools de delegación/escalamiento
    loop Decide → Act → Observe
        SupervisorLoop->>SupervisorLLM: prompt + observaciones
        SupervisorLLM-->>SupervisorLoop: AgentDecision JSON validado
        opt decisión action=tool
            SupervisorLoop->>SupervisorRegistry: run(ToolCall, contexto, política)
            SupervisorRegistry-->>SupervisorLoop: ToolResult
        end
    end
    Supervisor-->>Graph: PlanResult(sources, instruction)

    Graph->>Produce: produce(state)
    Produce->>Requirements: run_requerimientos(goal, provider, library, retriever, board)
    Requirements->>Toolkit: RequirementsToolkit(library, retriever, board)
    Requirements->>ReqRegistry: build_catalog_registry(implementations)
    Requirements->>ReqLoop: run_basic_agent(goal, registry, decider, límites)
    loop Decide → Act → Observe
        ReqLoop->>ReqLLM: objetivo + tools disponibles + observaciones
        ReqLLM-->>ReqLoop: AgentDecision JSON validado
        opt action=tool
            ReqLoop->>ReqRegistry: run(ToolCall)
            Note over ReqRegistry: disponibilidad → Pydantic → autorización → ejecución
            alt ingestar_y_fragmentar
                ReqRegistry->>Toolkit: ingestar_y_fragmentar(IngestArgs)
                Toolkit->>Library: load(document_id)
                Toolkit->>Retriever: index(build_chunks(document))
            else buscar_en_fuentes
                ReqRegistry->>Toolkit: buscar_en_fuentes(SearchArgs)
                Toolkit->>Retriever: hybrid_search(query, top_k, filters)
                Retriever-->>Toolkit: SearchResult[]
            else redactar_historia
                ReqRegistry->>Toolkit: redactar_historia(DraftArgs)
                Toolkit->>Retriever: get(chunk_id)
                Retriever-->>Toolkit: SearchResult / metadata
                Toolkit->>Board: add_item(BacklogItem)
            end
            Toolkit-->>ReqRegistry: ToolResult
            ReqRegistry-->>ReqLoop: ToolResult (observación)
        end
    end
    ReqLoop-->>Requirements: answer, trace, stop_reason, observations
    Requirements-->>Produce: outcome + tokens
    Produce->>Board: serializa tablero y calcula ítems borrador
    Produce-->>Graph: board, pending, tokens, trace
    Graph-->>Operador: estado de corrida o pausa HITL
```

**Alcance del dibujo:** después de `produce`, el grafo pasa por revisión del
Crítico, auditoría y los nodos de decisión/integración configurados. No se
despliegan aquí porque el foco es la producción de requerimientos.

## 2. Clases, contratos y métodos existentes

`●` indica que el método tiene implementación funcional en este flujo; `◐`
indica que su resultado depende de otro componente o que el contrato permite
respuestas no implementadas. No hay una clase `AgentFactory`: la composición
se realiza con `build_graph`, `make_nodes`, `plan_run` y `run_requerimientos`.

```mermaid
classDiagram
    class RunDeps {
        +Providers providers
        +SourceLibrary library
        +Retriever retriever
        +ProjectMemory memory
        +PolicyConfig policy
        +RunBudget budget
        +BacklogGateway backlog
        +PublicationLedger ledger
    }
    class Providers {
        +LLMProvider supervisor
        +LLMProvider requerimientos
        +LLMProvider critico
        +LLMProvider auditor
        +LLMProvider integracion
    }
    class GraphBuilder {
        +build_graph(deps, checkpointer) ●
        +run_pipeline(graph, objective, thread_id) ●
        +resume_pipeline(graph, thread_id, decision) ●
    }
    class Nodes {
        +make_nodes(deps) ●
        +plan(state) ●
        +produce(state) ●
    }
    class Supervisor {
        +plan_run(objective, provider, library, policy) ●
        +drafting_sources(library) ●
        +summarize_run(facts, provider) ●
    }
    class RequirementsAgent {
        +run_requerimientos(goal, provider, library, retriever, board) ●
        +revise_item(item_id, objections, kwargs) ●
    }
    class LLMDecider {
        +build_prompt(user_message, observations) ●
        +_parse(text) ●
        +__call__(user_message, observations) ●
    }
    class AgentDecision {
        +action: tool | final
        +tool_name: str | None
        +arguments: dict
        +final_answer: str | None
    }
    class AgentLoop {
        +run_basic_agent(message, registry, decide_next, limits) ●
        +sanitize_for_trace(value) ●
    }
    class LLMProvider {
        <<Protocol>>
        +generate(prompt, system, temperature) GenerationResult
        +agenerate(prompt, system, temperature) GenerationResult
    }
    class ToolRegistry {
        +register(tool) ●
        +available_tools(context, policy) ●
        +function_declarations(context, policy) ●
        +run(call, context, policy) ●
    }
    class ToolPolicy {
        +allowed_tools(registry, context) ●
        +authorize(context, tool, args) ●
    }
    class RequirementsToolkit {
        +implementations() ●
        +ingestar_y_fragmentar(args) ●
        +buscar_en_fuentes(args) ●
        +redactar_historia(args) ●
        +- _revise(args, citations) ●
    }
    class ToolArgs {
        <<Pydantic>>
        +IngestArgs(document_id)
        +SearchArgs(query, top_k, source_type, document_id)
        +DraftArgs(revises, parent_id, kind, title, description, acceptance_criteria, citations)
        +CitationRef(chunk_id, quote)
    }
    class ToolContracts {
        <<Pydantic>>
        +ExecutionContext(user_id, role, run_id, flags)
        +ToolCall(tool_name, arguments)
        +ToolResult(ok, content, metadata)
    }
    class SourceLibrary {
        +list_ids() ●
        +describe() ●
        +load(document_id) ●
        +write(document_id, metadata, text) ●
    }
    class SourceDocument {
        <<Pydantic>>
        +document_id: str
        +metadata: SourceMetadata
        +text: str
    }
    class Retriever {
        <<Protocol-like implementations>>
        +index(chunks) ●
        +hybrid_search(query, top_k, filters) ●
        +get(chunk_id) ●
    }
    class SearchResult {
        +chunk_id: str
        +document_id: str
        +text: str
        +score: float
        +page: int | None
        +metadata: dict
    }
    class Board {
        <<Pydantic>>
        +items: dict[str, BacklogItem]
        +add_item(item) ●
        +add_finding(finding) ●
        +post_message(message) ●
    }
    class BacklogItem {
        <<Pydantic>>
        +id: str
        +kind: ItemKind
        +title: str
        +description: str
        +acceptance_criteria: list[str]
        +citations: list[Citation]
        +state: ItemState
        +transition_to(new_state, actor) ●
    }
    class Citation {
        <<Pydantic>>
        +fragment_id: str
        +quote: str
        +source_name: str
        +source_type: SourceType
        +source_date: date
        +speaker: str | None
        +page: int | None
    }

    GraphBuilder --> RunDeps
    GraphBuilder --> Nodes
    Nodes --> Supervisor
    Nodes --> RequirementsAgent
    RunDeps --> Providers
    Supervisor --> AgentLoop
    RequirementsAgent --> RequirementsToolkit
    RequirementsAgent --> LLMDecider
    RequirementsAgent --> ToolRegistry
    LLMDecider --> LLMProvider
    LLMDecider --> AgentDecision
    AgentLoop --> ToolRegistry
    ToolRegistry --> ToolPolicy
    ToolRegistry --> ToolContracts
    RequirementsToolkit --> ToolArgs
    RequirementsToolkit --> SourceLibrary
    RequirementsToolkit --> Retriever
    RequirementsToolkit --> Board
    SourceLibrary --> SourceDocument
    Retriever --> SearchResult
    Board --> BacklogItem
    BacklogItem --> Citation
```

### Implementado y marcadores

- Las tres tools del productor están conectadas a handlers reales por
  `RequirementsToolkit.implementations()`. Sus argumentos y resultados usan
  modelos Pydantic, y las llamadas pasan por `ToolRegistry`.
- El catálogo declara 16 tools en total. Las que no se inyectan para un agente
  usan un handler que devuelve `not_implemented`; esto es un marcador, no una
  implementación funcional de esas herramientas.
- El proveedor concreto depende de configuración: se inyecta por `LLMProvider`
  (por ejemplo, `FakeProvider` para pruebas o proveedores externos en modo live).
- `summarize_run` tiene un resumen determinístico alternativo si falla el LLM;
  no es un stub.

## 3. Flujo de datos y llamadas a herramientas

```mermaid
flowchart TD
    SourceFiles["Fuentes .md con front matter YAML<br/>source_name, source_type, source_date, layout"]
    Library["SourceLibrary<br/>SourceDocument + SourceMetadata (Pydantic)"]
    Chunks["build_chunks<br/>fragmentos con chunk_id y metadata"]
    Embed["EmbeddingProvider"]
    Retriever["InMemoryRetriever o QdrantRetriever<br/>índice denso + búsqueda léxica BM25/RRF"]

    Goal["objective + instrucción + fuentes seleccionadas<br/>(RunState / nodo produce)"]
    Prompt["LLMDecider.build_prompt<br/>objetivo, declaraciones visibles, observaciones"]
    Provider["LLMProvider.generate<br/>Fake / Gemini / Anthropic según config"]
    Decision["AgentDecision Pydantic<br/>JSON: tool o final"]

    IngestArgs["IngestArgs Pydantic<br/>document_id"]
    SearchArgs["SearchArgs Pydantic<br/>query, top_k, filtros opcionales"]
    DraftArgs["DraftArgs Pydantic<br/>kind, title, descripción, criterios, citations"]
    Registry["ToolRegistry.run<br/>disponibilidad → validación → policy/rol → handler"]

    SearchResult["SearchResult[] → ToolResult<br/>texto y metadata del fragmento"]
    ChunkRef["CitationRef Pydantic<br/>chunk_id + quote"]
    Citation["Citation Pydantic<br/>metadata tomada del fragmento"]
    Item["BacklogItem Pydantic<br/>estado inicial BORRADOR"]
    Board["Board compartido<br/>serializado de vuelta a RunState"]
    Trace["trace + observations + stop_reason + tokens"]

    SourceFiles --> Library
    Library --> Chunks
    Chunks --> Embed
    Embed --> Retriever

    Goal --> Prompt
    Prompt --> Provider
    Provider --> Decision
    Decision --> ToolCall["ToolCall Pydantic<br/>tool_name + arguments"]
    ToolCall --> Registry
    IngestArgs --> Registry
    SearchArgs --> Registry
    DraftArgs --> Registry

    Registry -->|ingestar_y_fragmentar| Library
    Library -->|documento fuente| Chunks
    Chunks -->|index(chunks)| Retriever
    Registry -->|buscar_en_fuentes| Retriever
    Retriever --> SearchResult
    SearchResult -->|observación al siguiente turno| Prompt
    DraftArgs -->|citations| ChunkRef
    ChunkRef -->|get(chunk_id)| Retriever
    Retriever --> Citation
    Registry -->|redactar_historia| Citation
    Citation --> Item
    Item --> Board
    Board --> Trace
    Registry -->|ToolResult| Trace
    Decision -->|action=final| Trace
```

### Contratos y límites observables

- `SourceLibrary` solo resuelve identificadores de fuente, valida su metadata y
  carga archivos de su carpeta controlada. `build_graph` indexa **todas** las
  fuentes existentes, incluida la preventa. `plan_run` selecciona como fuentes
  de redacción solo reuniones y minutas, y el prompt de producción prohíbe usar
  la preventa; el retriever del productor, sin embargo, también contiene los
  fragmentos de preventa y los filtros de búsqueda son opcionales. La exclusión
  está guiada por plan/prompt, no impuesta como filtro obligatorio por el
  `RequirementsToolkit`.
- `redactar_historia` exige que cada `chunk_id` exista y construye la cita con
  metadata del fragmento, pero no comprueba que `quote` aparezca literalmente
  en su texto. La validación textual de la cita no forma parte de esta tool.
- `acceptance_criteria` se valida como Gherkin en `DraftArgs`; el ítem se agrega
  al tablero en estado `BORRADOR`. El paso de producción no lo aprueba.
- La búsqueda híbrida combina embeddings y BM25 mediante RRF; los embeddings
  dependen del `EmbeddingProvider` elegido en la configuración de runtime.
- `scripts/run_requerimientos.py` configura fuente, retriever y tablero e invoca
  directamente `run_requerimientos`; esa ruta de prueba no llama al Supervisor.

## Referencias de implementación

- Orquestación: [`graph/builder.py`](../../src/backlogguard/graph/builder.py),
  [`graph/nodes.py`](../../src/backlogguard/graph/nodes.py) y
  [`graph/deps.py`](../../src/backlogguard/graph/deps.py).
- Supervisor: [`agents/supervisor/__init__.py`](../../src/backlogguard/agents/supervisor/__init__.py).
- Productor: [`agents/requerimientos/__init__.py`](../../src/backlogguard/agents/requerimientos/__init__.py)
  y [`tools/requerimientos.py`](../../src/backlogguard/tools/requerimientos.py).
- Ciclo y tool runtime: [`agents/loop.py`](../../src/backlogguard/agents/loop.py),
  [`agents/decider.py`](../../src/backlogguard/agents/decider.py),
  [`tools/registry.py`](../../src/backlogguard/tools/registry.py) y
  [`tools/policy.py`](../../src/backlogguard/tools/policy.py).
- Fuentes, recuperación y tablero: [`rag/sources.py`](../../src/backlogguard/rag/sources.py),
  [`rag/retrieval.py`](../../src/backlogguard/rag/retrieval.py) y
  [`board/models.py`](../../src/backlogguard/board/models.py).
