# Framework Integrations — One Capture Owner Per Operation

Select exactly one capture layer for each operation. Do not combine a wrapper, callback handler, hook, processor, native framework telemetry, provider instrumentor, or manual span for the same call.

## Decision table

| Stack | Canonical capture owner | Do not add |
|---|---|---|
| Direct OpenAI / Anthropic / Google GenAI | `neatlogs.wrap(client)` | manual LLM trace or provider instrumentor for that client |
| Unsupported direct provider with a supported instrumentor | one `instrumentations=[...]` entry | wrapper/manual LLM trace for the same call |
| LangChain / LangGraph | `neatlogs.langchain_handler()` or the LangChain instrumentor—pick one | manual node/chain/LLM/tool/retriever spans |
| OpenAI Agents SDK | `neatlogs.openai_agents_processor()` | manual agent/LLM/tool/handoff/guardrail spans |
| CrewAI | `neatlogs.wrap(crew)` or its instrumentor—pick one | provider instrumentation for CrewAI-routed calls or manual task/tool/LLM spans |
| Pydantic AI / DSPy / Agno / Google ADK | the matching `neatlogs.wrap(...)` integration | manual spans around framework-owned runs, models, or tools |
| Strands | Strands native telemetry plus Neatlogs hooks/configuration | manual spans around native agent/model/tool operations |
| Raw HTTP / unsupported SDK with no instrumentor | one manual `trace(kind="LLM")` | any second capture layer |

## Custom orchestration

Capture ownership is per operation, not per application. A direct provider wrapper owns its model/embedding calls but does not own application functions that execute requested tools or perform custom retrieval, reranking, vector writes, guardrails, or evaluation. A framework integration may own more of those operations; consult its coverage before adding anything manually.

Use `@neatlogs.span(kind="WORKFLOW"|"CHAIN"|"AGENT")` around application-owned, multi-step orchestration. The captured framework/provider spans nest underneath it. Do not add a manual parent only to make one automatically captured call render; supported capture layers self-root when needed.

Valid examples:

- A custom `WORKFLOW` calls a custom `RETRIEVER` and then `neatlogs.wrap(OpenAI())`: the workflow parents one retriever and one wrapper-owned LLM span.
- A custom `CHAIN` performs preprocessing, invokes a wrapped Pydantic AI agent, and post-processes its result: the agent-owned hierarchy nests under the chain.
- A direct OpenAI model requests `lookup_order`; the wrapper records the request on the LLM span, while the application dispatcher uses one `TOOL` span for the actual function execution.

Invalid examples:

- A manual `LLM` trace around a wrapped client call.
- A manual node/tool/retriever span already emitted by the LangChain handler.
- A provider instrumentor around model calls routed through a framework wrapper that already emits LLM spans.

For unsupported/raw operations and their canonical attributes, use [`decorators-and-traces.md`](decorators-and-traces.md). `LLM` is root-eligible; current SDK manual APIs add one `WORKFLOW` parent for any other standalone non-root semantic kind. Use `@span(kind="EVALUATOR")` or `@span(kind="MEMORY")` for ordinary custom functions. Use `trace()` only for the decorator-rejected `LLM`, `RERANKER`, and `VECTOR_STORE` kinds, or when a raw/custom operation has no decorator boundary or needs direct canonical metadata, such as a DeepEval callback.

## Root behavior

The integration need not literally emit a `WORKFLOW`. It must produce a parentless root eligible for finalization:

| Capture owner | Standalone root behavior |
|---|---|
| Direct provider `wrap(...)` and supported provider instrumentors | a parentless LLM is the root; a non-root provider operation receives a `WORKFLOW` parent |
| LangChain handler | a chain/graph is a `CHAIN` root; a bare LLM is the root; a bare tool/retriever receives a `WORKFLOW` parent |
| OpenAI Agents processor / Google ADK runner / CrewAI crew or flow | emits `WORKFLOW` |
| Pydantic AI / Agno agent or team / Hermes / Claude Agent SDK | emits `AGENT` (Agno Workflow emits `WORKFLOW`) |
| DSPy module | emits `CHAIN`; a bare DSPy LLM/retriever must be invoked through its module or an explicit orchestration root |
| Strands native telemetry | `invoke_agent` is the `AGENT` root; this path requires the shared/global provider mode used by the Strands integration |
| Manual unsupported operation | a parentless LLM is the root; other standalone kinds receive a `WORKFLOW` parent |

## Verify

- [ ] Each real operation has exactly one capture owner.
- [ ] No manual LLM/tool/agent/node span duplicates automatic framework/provider coverage.
- [ ] Custom spans represent genuine application orchestration or unsupported operations.
- [ ] A runtime trace reaches the target project with the expected hierarchy and one LLM span per model call.
