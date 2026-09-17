#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.generate import main as generate_main  # noqa: E402
from evals.runner import load_cases, run_suite  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Jev golden evals")
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", default="eval-results/local/summary.json")
    args = parser.parse_args(argv)
    if args.generate:
        generate_main()
        return 0
    data_dir = Path(args.out).resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    summary = asyncio.run(run_suite(load_cases(), live=args.live, data_dir=data_dir))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
