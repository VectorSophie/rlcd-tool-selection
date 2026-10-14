import asyncio

import pytest

from rlcdselect.datasets.fixtures import core_tasks, load_fixtures
from rlcdselect.profiles import ARCHITECTURE_MATCHED_V1


@pytest.fixture
def fixtures():
    return load_fixtures()


@pytest.fixture
def tasks(fixtures):
    return {t.task_id: t for t in fixtures[1]}


@pytest.fixture
def core(fixtures):
    """Cross-arm tasks only (no decomposed-only stress tasks)."""
    return core_tasks(fixtures[1])


@pytest.fixture
def serialization():
    return ARCHITECTURE_MATCHED_V1


def run(coro):
    return asyncio.run(coro)
