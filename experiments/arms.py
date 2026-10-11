"""Shared helper: run one arm (a mode over an idea list). Sequential on purpose, so latency is comparable."""
import asyncio
from agent import loop


async def run_arm(ideas: list[str], mode: str, llm=None, repeats: int = 1, patch: str | None = None,
                  sleep_s: float = 0.0, runs_dir=None, emit=None, on_run=None) -> list[dict]:
    """Execute a list of ideas sequentially for a specified mode and repeat count.

    Autopsy is strictly disabled (autopsy=False) during A/B testing:
    Flight Recorder is a diagnostic tool, not part of production build cost.
    Failed runs are always preserved.
    """
    records = []
    for rep in range(1, repeats + 1):
        for idx, idea in enumerate(ideas, start=1):
            # autopsy=False: the Flight Recorder is a diagnostic tool, not part of the product's per-build cost.
            rec = await loop.run_build(
                idea=idea,
                mode=mode,
                llm=llm,
                template="tip_splitter",
                patch=patch,
                autopsy=False,
                runs_dir=runs_dir,
                emit=emit,
            )
            records.append(rec)  # failed runs are always kept
            if on_run:
                try:
                    on_run(rec, rep, idx, len(ideas))
                except TypeError:
                    on_run(rec)
            if sleep_s > 0:
                await asyncio.sleep(sleep_s)
    return records


def describe(rec: dict) -> str:
    succ = "PASS" if rec.get("success") else "FAIL"
    fa = "1st-pass" if rec.get("first_attempt_passed") else f"att={rec.get('attempts')}"
    return (f"{rec['mode']:<8} success={succ:<5} attempts={rec['attempts']} "
            f"first={fa:<8} cost=${rec.get('cost_usd')} run={rec['run_id']}")
