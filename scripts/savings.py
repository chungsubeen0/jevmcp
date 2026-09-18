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

from evals.savings import run_savings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Level B/C Jev vs frontier context proxies")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--out", default="eval-results/local/savings.json")
    args = parser.parse_args(argv)
    out = Path(args.out)
    data_dir = out.resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    summary = asyncio.run(run_savings(live=args.live, data_dir=data_dir))
    public = {key: value for key, value in summary.items() if key != "rows"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(public, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
