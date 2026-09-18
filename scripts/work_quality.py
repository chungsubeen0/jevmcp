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

from evals.work_quality import run_work_quality  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coding and planning work-preservation checks")
    parser.add_argument("--out", default="eval-results/local/work_quality.json")
    args = parser.parse_args(argv)
    out = Path(args.out)
    data_dir = out.resolve().parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    summary = asyncio.run(run_work_quality(data_dir))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["spec_lost_work"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
