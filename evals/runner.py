"""Eval harness: runs the 10 scripted scenarios end-to-end and checks expected tags."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from productpilot.graph import run_with_auto_approval
from .scenarios import build_scenarios


def run_evals(mock: bool | None = None, only: int | None = None) -> dict:
    if mock is not None:
        os.environ["PRODUCTPILOT_MOCK"] = "1" if mock else "0"
    try:
        from seed_memory import seed as seed_memory

        seed_memory()
    except Exception:
        pass

    scenarios = [s for s in build_scenarios() if only is None or s.id == only]
    results = []
    for sc in scenarios:
        t0 = time.time()
        try:
            state, interrupts = run_with_auto_approval(
                pm_input=sc.pm_input,
                source_paths=sc.sources,
                org_name="EvalCo",
            )
            error = None
        except Exception as exc:
            state, interrupts, error = {}, [], str(exc)
        passed, failures = (False, ["run_error"]) if error else sc.check(state, interrupts)
        duration = round(time.time() - t0, 2)
        results.append(
            {
                "id": sc.id,
                "name": sc.name,
                "category": sc.category,
                "pm_input": sc.pm_input,
                "sources": sc.sources,
                "expected_tag": sc.expected_tag,
                "passed": passed,
                "failures": failures,
                "error": error,
                "duration_s": duration,
                "interrupts": [i.get("type") for i in interrupts],
                "critic_scores": state.get("critic_scores", {}),
                "themes": state.get("themes", []),
                "options": state.get("options", []),
                "injection_flags": state.get("injection_flags", []),
                "contradictions": state.get("contradictions", []),
                "memory_hits": [{"title": h.get("title"), "source": h.get("source")} for h in state.get("memory_hits", [])],
                "compliance_dependencies": state.get("compliance_dependencies", []),
                "status": state.get("status"),
            }
        )
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r["passed"]),
        "failed": sum(1 for r in results if not r["passed"]),
        "categories": {
            "standard": sum(1 for r in results if r["category"] == "standard" and r["passed"]),
            "adversarial": sum(1 for r in results if r["category"] == "adversarial" and r["passed"]),
        },
        "results": results,
    }
    return summary


def print_report(summary: dict) -> None:
    from productpilot import config

    print(f"ProductPilot eval harness  (mock={config.MOCK})")
    print(f"{'ID':<4}{'Category':<12}{'Scenario':<48}{'Expected tag':<38}{'Result':<10}{'s':<7}")
    print("-" * 120)
    for r in summary["results"]:
        tag = r["expected_tag"]
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['id']:<4}{r['category']:<12}{r['name'][:46]:<48}{tag[:36]:<38}{status:<10}{r['duration_s']:<7}")
        if not r["passed"]:
            print(f"     └ failures: {r['failures']}")
    print("-" * 120)
    print(f"PASSED {summary['passed']}/{summary['total']}  (standard {summary['categories']['standard']} "
          f"/ adversarial {summary['categories']['adversarial']})")


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    import sys as _sys

    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="ProductPilot eval harness")
    parser.add_argument("--mock", choices=["0", "1"], default=None, help="override PRODUCTPILOT_MOCK")
    parser.add_argument("--only", type=int, default=None, help="run a single scenario by id")
    parser.add_argument("--report", default=None, help="write JSON report to path")
    args = parser.parse_args(argv)

    summary = run_evals(mock=bool(int(args.mock)) if args.mock else None, only=args.only)
    print_report(summary)
    if args.report:
        Path(args.report).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print(f"report written: {args.report}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())