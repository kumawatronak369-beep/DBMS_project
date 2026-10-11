import pytest

import config
from tests.conftest import SECRET_KEY


def test_defaults_when_nothing_is_set():
    settings = config.from_env({})
    assert settings.backend_url == "http://127.0.0.1:8000"
    assert settings.api_key == "" and not settings.has_api_key
    assert (settings.profile, settings.interval, settings.count) == ("lab-a", 2.0, 0)
    assert settings.duplicate_rate == 0.15 and settings.seed is None


def test_values_are_read_from_the_environment():
    settings = config.from_env(
        {
            "COLLECTOR_BACKEND_URL": "http://example.test:9000/",
            "COLLECTOR_API_KEY": f"  {SECRET_KEY} ",
            "COLLECTOR_PROFILE": "LIB-01",
            "COLLECTOR_INTERVAL": "0.5",
            "COLLECTOR_COUNT": "25",
            "COLLECTOR_DUPLICATE_RATE": "0.3",
            "COLLECTOR_TIMEOUT": "9",
            "COLLECTOR_MAX_ERRORS": "4",
            "COLLECTOR_SEED": "42",
        }
    )
    assert settings.backend_url == "http://example.test:9000"
    assert settings.api_key == SECRET_KEY and settings.has_api_key
    assert settings.profile == "lib-01"
    assert (settings.interval, settings.count, settings.duplicate_rate) == (0.5, 25, 0.3)
    assert (settings.timeout, settings.max_consecutive_errors, settings.seed) == (9.0, 4, 42)


def test_the_api_key_is_never_shown_in_repr_or_str():
    settings = config.from_env({"COLLECTOR_API_KEY": SECRET_KEY})
    assert SECRET_KEY not in repr(settings)
    assert SECRET_KEY not in str(settings)
    assert SECRET_KEY not in repr(settings.with_overrides(interval=1.0))


@pytest.mark.parametrize(
    "env, fragment",
    [
        ({"COLLECTOR_INTERVAL": "fast"}, "COLLECTOR_INTERVAL must be a number"),
        ({"COLLECTOR_INTERVAL": "-1"}, "COLLECTOR_INTERVAL must not be negative"),
        ({"COLLECTOR_COUNT": "many"}, "COLLECTOR_COUNT must be a whole number"),
        ({"COLLECTOR_COUNT": "-3"}, "COLLECTOR_COUNT must not be negative"),
        ({"COLLECTOR_DUPLICATE_RATE": "1.5"}, "between 0 and 1"),
        ({"COLLECTOR_TIMEOUT": "0"}, "COLLECTOR_TIMEOUT must be greater than 0"),
        ({"COLLECTOR_MAX_ERRORS": "0"}, "at least 1"),
        ({"COLLECTOR_SEED": "abc"}, "COLLECTOR_SEED must be a whole number"),
        ({"COLLECTOR_BACKEND_URL": "localhost:8000"}, "must start with http"),
    ],
)
def test_invalid_settings_give_a_clear_error_that_never_contains_the_key(env, fragment):
    with pytest.raises(config.ConfigError) as raised:
        config.from_env({**env, "COLLECTOR_API_KEY": SECRET_KEY})
    assert fragment in str(raised.value)
    assert SECRET_KEY not in str(raised.value)


def test_command_line_overrides_win_and_none_is_ignored():
    base = config.from_env({"COLLECTOR_INTERVAL": "5", "COLLECTOR_COUNT": "10"})
    changed = base.with_overrides(interval=0.5, count=None, profile=None)
    assert (changed.interval, changed.count, changed.profile) == (0.5, 10, "lab-a")
    assert base.with_overrides(count=0).count == 0
    with pytest.raises(config.ConfigError):
        base.with_overrides(duplicate_rate=2)


def test_env_file_fills_gaps_but_never_overrides_the_environment(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n\nCOLLECTOR_PROFILE=lab-b\nCOLLECTOR_API_KEY='from-file'\nCOLLECTOR_INTERVAL=9\nnot a setting\n",
        encoding="utf-8",
    )
    environ = {"COLLECTOR_INTERVAL": "1"}
    config.load_env_file(env_file, environ)
    assert environ == {
        "COLLECTOR_INTERVAL": "1",
        "COLLECTOR_PROFILE": "lab-b",
        "COLLECTOR_API_KEY": "from-file",
    }


def test_a_missing_env_file_is_fine(tmp_path):
    environ = {}
    config.load_env_file(tmp_path / "does-not-exist.env", environ)
    assert environ == {}
