import pytest

from skillgen.config import (
    AnalyzerKind,
    Environment,
    Settings,
    check_app_url,
    settings_from_dict,
    settings_to_dict,
    update_settings,
)
from skillgen.errors import ConfigError


def test_settings_round_trip():
    settings = Settings(
        app_name="Acme",
        app_url="http://localhost:3000",
        environment=Environment.STAGING,
        should_probe=True,
        include=("a/*",),
        analyzer=AnalyzerKind.FILE,
    )
    assert settings_from_dict(settings_to_dict(settings)) == settings


def test_settings_from_dict_fills_defaults():
    assert settings_from_dict({}) == Settings()


def test_settings_from_dict_rejects_bad_values():
    with pytest.raises(ConfigError):
        settings_from_dict({"environment": "moon"})


@pytest.mark.parametrize("url", ["localhost:3000", "ftp://x", "not a url"])
def test_check_app_url_rejects_non_http(url):
    with pytest.raises(ConfigError):
        check_app_url(url)


def test_check_app_url_strips_slash():
    assert check_app_url("https://app.example.com/") == "https://app.example.com"


def test_update_settings_validates_url():
    with pytest.raises(ConfigError):
        update_settings(Settings(), app_url="nope")
