"""neatlogs setup and span helpers. This is the ONLY module that imports neatlogs.

Every span is also recorded locally (name, type, duration_ms, tokens, cost_usd, status, error), so the
Flight Recorder always has a trace summary even if neatlogs export is limited or not configured.
"""
import time

import config

_enabled = False


def setup(workflow_name: str = "pocket-startup") -> bool:
    """Initialise neatlogs if NEATLOGS_API_KEY is set. Safe to call repeatedly. Returns True if enabled."""
    global _enabled
    if _enabled or not config.NEATLOGS_API_KEY:
        return _enabled
    try:
        import neatlogs
        neatlogs.init(api_key=config.NEATLOGS_API_KEY, workflow_name=workflow_name, tags=["neatHack"])
        _enabled = True
    except Exception as e:  # noqa: BLE001
        print(f"[tracing] neatlogs init failed, continuing with local spans only: {e}")
    return _enabled


def flush():
    if _enabled:
        try:
            import neatlogs
            neatlogs.flush()
        except Exception:  # noqa: BLE001
            pass


class Tracer:
    """One per run. Wraps awaited calls in a neatlogs span (when enabled) and records a local span."""

    def __init__(self, tags: list[str] | None = None, stats=None):
        self.tags = tags or []
        self.stats = stats
        self.spans: list[dict] = []

    async def span(self, name: str, kind: str, fn, *args, extra_tags=None, **kwargs):
        """kind: WORKFLOW | AGENT | CHAIN | TOOL (neatlogs OpenInference kinds)."""
        t0 = time.monotonic()
        tok0 = self.stats.tokens if self.stats else 0
        cost0 = self.stats.cost_usd if self.stats else 0.0
        rec = {"name": name, "type": kind, "duration_ms": 0, "tokens": 0, "cost_usd": 0.0, "status": "ok", "error": None}
        self.spans.append(rec)
        call = fn
        if _enabled:
            try:
                import neatlogs
                call = neatlogs.span(kind=kind, name=name, tags=self.tags + (extra_tags or []))(fn)
            except Exception:  # noqa: BLE001
                call = fn
        try:
            return await call(*args, **kwargs)
        except BaseException as e:
            rec["status"] = "error"
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            raise
        finally:
            rec["duration_ms"] = int((time.monotonic() - t0) * 1000)
            if self.stats:
                rec["tokens"] = self.stats.tokens - tok0
                if self.stats.cost_usd is not None and cost0 is not None and isinstance(self.stats.cost_usd, (int, float)) and isinstance(cost0, (int, float)):
                    rec["cost_usd"] = round(self.stats.cost_usd - cost0, 8)
                else:
                    rec["cost_usd"] = "UNPRICED"

    def summary(self) -> list[dict]:
        return list(self.spans)
