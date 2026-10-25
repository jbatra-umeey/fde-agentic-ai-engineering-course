import pytest
from jev_core.models import Principal
from jev_core.providers import FixturePlanner
from jev_core.runtime import Harness
from jev_core.store import Store
from jev_tools.registry import Registry
from jev_workflows.scenarios import seed


@pytest.fixture
def store(tmp_path):
    store = Store(str(tmp_path / "test.sqlite"))
    seed(store, "alpha")
    seed(store, "beta")
    return store


@pytest.fixture
def operator():
    return Principal(tenant="alpha", subject="alice", role="operator")


@pytest.fixture
def reviewer():
    return Principal(tenant="alpha", subject="bob", role="reviewer")


@pytest.fixture
def harness(store):
    h = Harness(store, Registry(), FixturePlanner())
    yield h
    h.telemetry.close()
