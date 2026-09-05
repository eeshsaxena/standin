import pytest

from standin.config import Config
from standin.exceptions import ConfigError
from standin.models import Mode
from standin.redaction import DefaultRedactor, NullRedactor


def test_mode_string_coerced_to_enum():
    assert Config(mode="none").mode is Mode.NONE
    assert Config(mode=Mode.ALL).mode is Mode.ALL


def test_invalid_mode_raises():
    with pytest.raises(ConfigError):
        Config(mode="teleport")


def test_redact_flag_selects_redactor():
    assert isinstance(Config(redact=True).redactor, DefaultRedactor)
    assert isinstance(Config(redact=False).redactor, NullRedactor)


def test_explicit_redactor_wins():
    r = NullRedactor()
    assert Config(redact=True, redactor=r).redactor is r
