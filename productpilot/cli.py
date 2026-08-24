"""CLI entrypoint: run the full agentic flow non-interactively (auto-approves checkpoints)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="productpilot", description="ProductPilot — agentic product consultant")
    parser.add_argument("--input", required=True, help="PM request, e.g. 'churn is high in month 2'")
    parser.add_argument("--sources", nargs="*", default=[], help="raw source files (CSV/JSON/MD)")
    parser.add_argument("--org", default="", help="company / org name")
    parser.add_argument("--auto-answer", default="The analytics product, new trial signups.", help="answer used at clarification checkpoints")
    parser.add_argument("--fail-below", type=float, default=None, help="exit non-zero if the Critic overall score is below this value")
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args(argv)

    from . import config
    from .graph import run_with_auto_approval
    from .memory.stores import sqlite_store, vector_store

    print("ProductPilot")
    print(f"  memory: {config.SQLITE_PATH.name} + vector index ({vector_store().backend}, {vector_store().count()} docs)")

    try:
        result, interrupts = run_with_auto_approval(
            pm_input=args.input,
            source_paths=args.sources,
            org_name=args.org,
            auto_answer=args.auto_answer,
        )
    except Exception as exc:
        print(f"error: run failed — {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({"ok": False, "error": str(exc)}))
        return 2

    flags = result.get("injection_flags", [])
    if flags:
        print(f"  ⚠ {len(flags)} prompt-injection attempt(s) quarantined (never forwarded to the model)")
        for f in flags[:3]:
            print(f"     - {f.get('reason')} in {f.get('source')}")
    missing = [p for p in args.sources if not Path(p).exists()]
    if missing:
        print(f"  ⚠ {len(missing)} source file(s) not found (recorded in the trace): {missing}")

    if args.json:
        report = {
            "ok": True,
            "pm_input": args.input,
            "sources": args.sources,
            "interrupts": [i.get("type") for i in interrupts],
            "themes": result.get("themes", []),
            "options": result.get("options", []),
            "critic_scores": result.get("critic_scores", {}),
            "prd_id": result.get("prd_id"),
            "status": result.get("status"),
            "prd_draft": result.get("prd_draft", ""),
            "injection_flags": flags,
            "memory_hits": result.get("memory_hits", []),
            "trace": result.get("trace", {}),
        }
        print(json.dumps(report, indent=2, default=str))
    else:
        print("\n=== Planner ===")
        if interrupts and interrupts[0].get("type") == "clarification":
            print(f"  clarification requested: {interrupts[0]['question']}")
        print("\n=== Research synthesis ===")
        for t in result.get("themes", []):
            print(f"  - {t.get('name')} ({t.get('sentiment')}) — {t.get('frequency')} mentions")
        for c in result.get("contradictions", []):
            print(f"  ⚠ contradiction: {c.get('name')} — {c.get('detail')}")
        print("\n=== RICE options ===")
        for o in result.get("options", []):
            print(f"  - {o.get('name')}: RICE {o.get('rice')} (confidence {o.get('confidence_label')})")
        print("\n=== Critic ===")
        scores = result.get("critic_scores", {})
        for dim, score in scores.items():
            print(f"  {dim}: {score}")
        print(f"  overall: {scores.get('overall')}")
        print("\n=== PRD ===")
        print(result.get("prd_draft", "(no draft)"))
        print(f"\ncommitted as PRD #{result.get('prd_id')} | status={result.get('status')}")
        recent = sqlite_store().list_prds(3)
        for r in recent:
            print(f"  memory: #{r['id']} {r['title']} (critic {r['critic_overall']})")

    if args.fail_below is not None:
        overall = result.get("critic_scores", {}).get("overall")
        if overall is None or overall < args.fail_below:
            print(f"critic overall {overall} is below --fail-below {args.fail_below}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())