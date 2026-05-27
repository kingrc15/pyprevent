from __future__ import annotations

import pytest

from tests.factories import make_prevent_row


@pytest.fixture
def prevent_row():
    return make_prevent_row
