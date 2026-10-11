"""Quick smoke run: python -m experiments.smoke --mode baseline --n 1"""
import argparse
import asyncio
import sys

import config
from agent import loop, tracing
from agent.llm import LLM
from experiments.ideas import TUNING


def parse_args(args=None):
    ap = argparse.ArgumentParser(description="Run Pocket Startup smoke test.")
    ap.add_argument("--mode", choices=["baseline", "improved"], default="baseline",
                    help="Prompt mode (baseline or improved)")
    ap.add_argument("--n", type=int, default=1,
                    help="Number of runs to execute (default: 1)")
    ap.add_argument("--idea", type=str, default=None,
                    help="Custom startup idea (optional; defaults to TUNING ideas)")
    ap.add_argument("--mock", action="store_true",
                    help="Run with offline MockLLM (labelled MOCK, excluded from real metrics)")
    return ap.parse_args(args)


async def run_smoke(mode: str = "baseline", n: int = 1, mock: bool = False,
                    idea: str | None = None, emit=None) -> list[dict]:
    # 1. Tracing initialization before LLM creation
    tracing.setup()

    # 2. Select LLM
    if mock:
        from agent.mock_llm import MockLLM
        llm = MockLLM()
    else:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env or pass --mock for offline verification.")
        llm = LLM()

    results = []
    default_emit = emit or (lambda t, d: print(f"  [{t}] {str(d)[:110]}"))

    for i in range(n):
        run_idea = idea or TUNING[i % len(TUNING)]
        print(f"\n--- Smoke Run {i + 1}/{n}: mode={mode} mock={mock} ---")
        print(f"Idea: {run_idea}")

        rec = await loop.run_build(
            run_idea,
            mode,
            default_emit,
            llm=llm,
            template="tip_splitter",
        )
        results.append(rec)

        mock_label = " [MOCK - excluded from metrics]" if rec["mock"] else ""
        rails_fired = [r["rail"] for r in rec["rails_fired"]]
        print(
            f"Run ID: {rec['run_id']}{mock_label}\n"
            f"  Outcome: {'SUCCESS' if rec['success'] else 'FAILED'}\n"
            f"  Attempts: {rec['attempts']} (First attempt passed: {rec['first_attempt_passed']})\n"
            f"  Tokens: {rec['tokens']} (in: {rec['input_tokens']}, out: {rec['output_tokens']}) [MEASURED]\n"
            f"  Cost: ${rec['cost_usd']:.6f} [COMPUTED: {rec['pricing_date']}]\n"
            f"  Latency: {rec['latency_s']}s [MEASURED]\n"
            f"  Rails fired: {rails_fired or 'none'}"
        )
        if rec.get("error"):
            print(f"  Error: {rec['error']}")

    return results


def main(args=None):
    parsed = parse_args(args)
    try:
        return asyncio.run(run_smoke(
            mode=parsed.mode,
            n=parsed.n,
            mock=parsed.mock,
            idea=parsed.idea,
        ))
    except Exception as e:
        print(f"Smoke run error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
