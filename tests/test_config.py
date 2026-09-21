"""Configuration must fail loudly; a silent default pointed at the wrong core
is worse than a crash on startup.
"""

import importlib

import pytest


def reload_config(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    from simulator import config

    return importlib.reload(config)


def test_slice_profile_map_parses(monkeypatch):
    config = reload_config(monkeypatch, SLICE_PROFILE_MAP="0=6,1=7")
    assert config.slice_profile_map() == {0: 6, 1: 7}


def test_slice_profile_map_rejects_garbage(monkeypatch):
    config = reload_config(monkeypatch, SLICE_PROFILE_MAP="zero=six")
    with pytest.raises(ValueError):
        config.slice_profile_map()


def test_no_real_endpoint_or_credential_is_baked_in(monkeypatch):
    monkeypatch.delenv("RAEMIS_API_URL", raising=False)
    monkeypatch.delenv("RAEMIS_USERNAME", raising=False)
    monkeypatch.delenv("RAEMIS_PASSWORD", raising=False)
    from simulator import config

    config = importlib.reload(config)
    # RFC 5737 documentation range only.
    assert "192.0.2." in config.RAEMIS_API_URL
    assert config.raemis_auth() is None


def test_auth_appears_once_credentials_are_set(monkeypatch):
    config = reload_config(monkeypatch, RAEMIS_USERNAME="u", RAEMIS_PASSWORD="p")
    assert config.raemis_auth() == ("u", "p")
