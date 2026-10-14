import asyncio

import pytest

from rlcdselect.core.serialization import NamePolicy, SerializationConfig
from rlcdselect.datasets.fixtures import load_fixtures


@pytest.fixture
def fixtures():
    return load_fixtures()


@pytest.fixture
def tasks(fixtures):
    return {t.task_id: t for t in fixtures[1]}


@pytest.fixture
def serialization():
    return SerializationConfig(name_policy=NamePolicy.QUALIFY_ON_COLLISION)


def run(coro):
    return asyncio.run(coro)
