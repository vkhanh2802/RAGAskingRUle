import pytest
from pydantic import ValidationError

from regularag.core.config import Settings


def test_settings_reject_non_positive_database_timeout() -> None:
    with pytest.raises(ValidationError):
        Settings(database_connect_timeout_seconds=0)
