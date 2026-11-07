"""Run the pre-registered Lane A comparison and write the result next to this folder."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kok_a.experiment import run_experiment, summarize  # noqa: E402
from kok_a.snapshot import SNAPSHOT_READY  # noqa: E402


def main() -> None:
    result = run_experiment("btc-trend-24-72-demo", SNAPSHOT_READY)
    out = ROOT / "experiments"
    out.mkdir(exist_ok=True)
    path = out / "last_experiment.json"
    path.write_text(result.model_dump_json(indent=2))
    print(summarize(result))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
