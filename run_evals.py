"""ProductPilot eval harness — run 10 scripted scenarios and check expected tags.

Usage:
  python run_evals.py                     # real models (needs ANTHROPIC_API_KEY, TAVILY_API_KEY)
  python run_evals.py --only 8            # single scenario
  python run_evals.py --report evals/report.json
"""
from __future__ import annotations

import sys

from evals.runner import main

if __name__ == "__main__":
    sys.exit(main())