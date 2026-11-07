import pytest

from kok_a.experiment import assemble
from kok_a.market import SNAPSHOT_SYNTHETIC


@pytest.fixture(scope="session")
def bundle():
    return assemble(
        "btc-trend-24-72-demo",
        SNAPSHOT_SYNTHETIC,
        n=1100,
        seed=7,
        n_boot=30,
        n_estimators=40,
    )
