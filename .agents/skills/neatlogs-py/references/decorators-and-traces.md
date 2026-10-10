# Manual Instrumentation — NeatLogs Python SDK

Manual instrumentation is for application-owned orchestration and operations that no supported integration captures. Choose the capture owner **per operation**. A provider wrapper may own an LLM call while the application still owns a custom tool, retriever, reranker, evaluator, or vector-store write.

Never add a manual span of the same semantic kind around a call already captured by a wrapper, callback handler, hook, processor, native framework span, or provider instrumentor.

## Root requirement

A completed trace must contain a parentless `WORKFLOW`, `CHAIN`, `AGENT`, `MCP_TOOL`, or `LLM` span. Current SDK manual APIs add one `WORKFLOW` parent when a standalone `TOOL`, `RETRIEVER`, `RERANKER`, `EMBEDDING`, `VECTOR_STORE`, `GUARDRAIL`, `EVALUATOR`, or `MEMORY` would otherwise be parentless. Nested calls keep their real parent. Add an explicit orchestration root when several operations belong to one run, not merely to make one operation render.

```python
@neatlogs.span(kind="WORKFLOW", name="answer_question")
def answer_question(query: str):
    docs = retrieve(query)  # custom RETRIEVER child
    return wrapped_client.chat.completions.create(...)  # wrapper-owned LLM child
```

Do not add an otherwise meaningless root around a single supported wrapped call merely to make it render; supported wrappers already self-root. The explicit root above is useful because the function genuinely orchestrates retrieval plus generation.

## `@neatlogs.span()` for custom functions

`@span()` accepts `WORKFLOW`, `AGENT`, `CHAIN`, `TOOL`, `RETRIEVER`, `EMBEDDING`, `GUARDRAIL`, `EVALUATOR`, `MEMORY`, and `MCP_TOOL`. It captures function input/output and errors. `RETRIEVER` also extracts a `query`/`question`/`text` argument and returned documents.

```python
@neatlogs.span(kind="TOOL", tool_name="lookup_account")
def lookup_account(account_id: str):
    return database.lookup(account_id)

@neatlogs.span(kind="RETRIEVER", name="search_knowledge_base")
def search_knowledge_base(query: str, top_k: int = 5):
    return custom_store.search(query, top_k=top_k)

@neatlogs.span(kind="EVALUATOR", name="answer_quality")
def evaluate_answer(answer: str, reference: str):
    return {"score": custom_evaluator(answer, reference)}

@neatlogs.span(kind="MEMORY", name="save_memory")
def save_memory(user_id: str, fact: str):
    return memory_store.save(user_id, fact)
```

Use these only when the operation is not framework-owned. For example, `neatlogs.wrap(OpenAI())` captures OpenAI model and embedding calls and records tool-call requests on the LLM span, but it cannot execute the application function selected by that request. A custom dispatcher function still needs one `TOOL` span. An OpenAI Agents processor, by contrast, owns the framework's actual tool execution span too, so do not decorate that tool again.

Do not decorate a one-line pass-through to an automatically captured call. Use `WORKFLOW`, `AGENT`, or `CHAIN` only when the function genuinely performs that orchestration.

## `neatlogs.trace()` for rejected kinds or direct metadata

Only `LLM`, `RERANKER`, and `VECTOR_STORE` are rejected by `@span()`. Use `trace()` for those kinds, or when a raw/custom operation has no decorator boundary or must set canonical attributes directly. For example, a DeepEval lifecycle callback may use `trace(kind="EVALUATOR")`; an ordinary application-owned evaluator function should use `@span(kind="EVALUATOR")` for automatic input/output and error capture. The chosen primitive is the operation's sole span, not an extra layer inside an `@span` for the same operation.

The tables below list the canonical attributes to set when known. Always record the operation input/output. For a manual `trace()`, catch failures long enough to call `span.record_exception(exc)` and `span.set_status(Status(StatusCode.ERROR, str(exc)))`, then re-raise. Keep the context open through complete stream consumption.

| Kind | Exact canonical attributes |
|---|---|
| `LLM` | Required when available: `neatlogs.llm.provider`, `neatlogs.llm.model_name`, `neatlogs.llm.input_messages.{i}.role`, `neatlogs.llm.input_messages.{i}.content`, `neatlogs.llm.output_messages.{i}.role`, `neatlogs.llm.output_messages.{i}.content`, `neatlogs.llm.token_count.prompt`, `neatlogs.llm.token_count.completion`, `neatlogs.llm.token_count.total`. Also report `neatlogs.llm.system`, `neatlogs.llm.finish_reason` or `neatlogs.llm.stop_reason`, `neatlogs.llm.is_streaming`, `neatlogs.llm.temperature`, `neatlogs.llm.top_p`, `neatlogs.llm.top_k`, `neatlogs.llm.max_tokens`, and `neatlogs.llm.invocation_parameters` when known. |
| `RETRIEVER` | `neatlogs.retriever.query`, `neatlogs.retriever.top_k`, `neatlogs.retriever.documents.{i}`, `neatlogs.retriever.input`, `neatlogs.retriever.output` |
| `RERANKER` | `neatlogs.reranker.model_name`, `neatlogs.reranker.query`, `neatlogs.reranker.top_k`, `neatlogs.reranker.input_documents.{i}`, `neatlogs.reranker.output_documents.{i}`, `neatlogs.reranker.input`, `neatlogs.reranker.output` |
| `VECTOR_STORE` | `neatlogs.db.system`, `neatlogs.db.operation`, `neatlogs.db.collection_name`, `neatlogs.vectordb.index_name`, `neatlogs.vectordb.embedding_model`, `neatlogs.vectordb.vector_dimension`, `neatlogs.vectordb.similarity_algorithm`, `neatlogs.vector_store.input`, `neatlogs.vector_store.output` |
| `EMBEDDING` | `neatlogs.embedding.model_name`, `neatlogs.embedding.text`, `neatlogs.embedding.token_count`, `neatlogs.embedding.vector`, `neatlogs.embedding.invocation_parameters`, `neatlogs.embedding.input`, `neatlogs.embedding.output` |
| `GUARDRAIL` | `neatlogs.guardrail.input`, `neatlogs.guardrail.output`, `neatlogs.guardrail.passed`, `neatlogs.guardrail.score` |
| `EVALUATOR` | `neatlogs.evaluator.input`, `neatlogs.evaluator.output`; encode evaluator name, criteria, and score in the JSON `neatlogs.metadata` attribute until dedicated evaluator fields exist |
| `TOOL` | `neatlogs.tool.name`, `neatlogs.tool.description`, `neatlogs.tool.parameters`, `neatlogs.tool.input`, `neatlogs.tool.output` |

Use indexed document keys. Do not emit the legacy `neatlogs.retrieval.*` namespace or invented keys such as `neatlogs.vector_store.query`.

### Unsupported/raw LLM

```python
import json
import neatlogs
from opentelemetry.trace import Status, StatusCode

with neatlogs.trace("raw_provider_request", kind="WORKFLOW"):
    with neatlogs.trace(
        "unsupported_provider.chat",
        kind="LLM",
        **{"neatlogs.internal": False},
    ) as span:
        span.set_attribute("neatlogs.llm.provider", "unsupported_provider")
        span.set_attribute("neatlogs.llm.model_name", model)
        span.set_attribute("neatlogs.llm.input_messages.0.role", "user")
        span.set_attribute("neatlogs.llm.input_messages.0.content", prompt)

        try:
            response = call_unsupported_provider(prompt, stream=False)
            span.set_attribute("neatlogs.llm.output_messages.0.role", "assistant")
            span.set_attribute("neatlogs.llm.output_messages.0.content", response.text)
            span.set_attribute("neatlogs.llm.token_count.prompt", response.usage.input_tokens)
            span.set_attribute("neatlogs.llm.token_count.completion", response.usage.output_tokens)
            span.set_attribute("neatlogs.llm.token_count.total", response.usage.total_tokens)
            span.set_attribute("neatlogs.llm.finish_reason", response.finish_reason)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
```

For streaming, set `neatlogs.llm.is_streaming = True`, keep the LLM context open while consuming the stream, accumulate the final output and usage, then set them before leaving the context. Do not close the span when only the stream handle has been returned.

### Retriever, reranker, and vector-store write

```python
with neatlogs.trace("search", kind="RETRIEVER") as span:
    span.set_attribute("neatlogs.retriever.query", query)
    span.set_attribute("neatlogs.retriever.top_k", top_k)
    span.set_attribute("neatlogs.retriever.input", json.dumps({"query": query, "top_k": top_k}))
    docs = custom_store.search(query, top_k=top_k)
    for i, doc in enumerate(docs):
        span.set_attribute(f"neatlogs.retriever.documents.{i}", json.dumps(doc, default=str))
    span.set_attribute("neatlogs.retriever.output", json.dumps(docs, default=str))

with neatlogs.trace("rerank", kind="RERANKER") as span:
    span.set_attribute("neatlogs.reranker.model_name", reranker_model)
    span.set_attribute("neatlogs.reranker.query", query)
    span.set_attribute("neatlogs.reranker.top_k", top_n)
    span.set_attribute("neatlogs.reranker.input", json.dumps({"query": query, "documents": docs}, default=str))
    for i, doc in enumerate(docs):
        span.set_attribute(f"neatlogs.reranker.input_documents.{i}", json.dumps(doc, default=str))
    ranked = custom_reranker(query, docs, top_n)
    for i, doc in enumerate(ranked):
        span.set_attribute(f"neatlogs.reranker.output_documents.{i}", json.dumps(doc, default=str))
    span.set_attribute("neatlogs.reranker.output", json.dumps(ranked, default=str))

with neatlogs.trace("upsert_documents", kind="VECTOR_STORE") as span:
    span.set_attribute("neatlogs.db.system", "custom_vector_db")
    span.set_attribute("neatlogs.db.operation", "upsert")
    span.set_attribute("neatlogs.vectordb.index_name", index_name)
    span.set_attribute("neatlogs.vector_store.input", json.dumps(docs, default=str))
    result = custom_store.upsert(docs)
    span.set_attribute("neatlogs.vector_store.output", json.dumps(result, default=str))
```

A vector search is normally `RETRIEVER`; use `VECTOR_STORE` for writes and index-management operations.

### Embedding and guardrail with direct metadata

```python
with neatlogs.trace("embed", kind="EMBEDDING") as span:
    span.set_attribute("neatlogs.embedding.model_name", embedding_model)
    span.set_attribute("neatlogs.embedding.text", text)
    span.set_attribute("neatlogs.embedding.input", json.dumps({"text": text}))
    vector = custom_embedder(text)
    span.set_attribute("neatlogs.embedding.output", json.dumps({"dimensions": len(vector)}))

with neatlogs.trace("safety_check", kind="GUARDRAIL") as span:
    span.set_attribute("neatlogs.guardrail.input", text)
    result = custom_guardrail(text)
    span.set_attribute("neatlogs.guardrail.passed", result.passed)
    span.set_attribute("neatlogs.guardrail.score", result.score)
    span.set_attribute("neatlogs.guardrail.output", json.dumps(result, default=str))
```

For a DeepEval callback or adapter with no application-owned function boundary to decorate, `trace(kind="EVALUATOR")` may instead be the sole owner so it can set `neatlogs.evaluator.input`, `neatlogs.evaluator.output`, and JSON `neatlogs.metadata` directly. Do not wrap an `@span(kind="EVALUATOR")` evaluator with that trace.

## One capture owner and valid composition

- Supported wrapper/handler/hook/processor + custom outer `WORKFLOW`/`CHAIN`/`AGENT`: valid when the parent represents real multi-step application orchestration.
- Supported LLM capture + application-owned `TOOL`/`RETRIEVER`/`RERANKER`/`GUARDRAIL`/`EVALUATOR`: valid when that integration does not already capture the operation.
- Manual semantic trace inside an `@span` for the same operation: duplicate; choose one.
- Provider wrapper/instrumentor around a framework-routed model call already captured by the framework: duplicate; remove one capture owner.

## `neatlogs.log()` and lifecycle

Use `neatlogs.log()` inside an active Neatlogs span and enable `capture_logs=True` when logs should export. `@span()` supports sync and async functions; `trace()` is a synchronous context manager that may contain awaited code. Scripts must flush/shutdown; servers initialize once and flush/shutdown during process shutdown.

## Verification

- [ ] Every trace has one eligible root; standalone non-root manual spans receive one automatic workflow parent.
- [ ] Every real operation has exactly one semantic capture owner.
- [ ] Unsupported operations populate the canonical kind-specific attributes above.
- [ ] Streaming spans remain open until final output/usage or cancellation/error.
- [ ] A live trace contains the intended hierarchy and no duplicate LLM/tool/retrieval spans.
