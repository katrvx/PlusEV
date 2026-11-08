"""Download the frozen Binance spot and Fear & Greed snapshot into A/fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from kok_a.snapshot import fetch_ready_snapshot  # noqa: E402


def main() -> None:
    manifest = fetch_ready_snapshot()
    print(
        f"{manifest['id']}: {manifest['n_bars']} bars, "
        f"{manifest['n_gaps_over_1h']} gaps, hash {manifest['market_hash']}"
    )
    print(f"fear & greed rows: {manifest['fear_greed_rows']}")


if __name__ == "__main__":
    main()
