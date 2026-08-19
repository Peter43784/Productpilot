"""ProductPilot eval harness — run 10 scripted scenarios and check expected tags.

Usage:
  python run_evals.py                     # mock mode (offline, deterministic)
  python run_evals.py --mock 0            # real models (needs API keys)
  python run_evals.py --only 8            # single scenario
  python run_evals.py --report evals/report.json
"""
from __future__ import annotations

import sys

from evals.runner import main

if __name__ == "__main__":
    sys.exit(main())