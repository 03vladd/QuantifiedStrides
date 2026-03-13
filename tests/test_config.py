"""Tests for config.py — environment variable loading and validation."""

import os
import pytest
from unittest.mock import patch


class TestConfigLoading:
    def test_required_vars_present(self):
        import config
        assert config.GARMIN_EMAIL == "test@example.com"
        assert config.GARMIN_PASSWORD == "testpassword"
        assert config.OPENWEATHER_API_KEY == "test_api_key"
        assert config.DB_USER == "quantified"
        assert config.DB_PASSWORD == "2026"

    def test_db_defaults(self):
        import config
        assert config.DB_HOST == "localhost"
        assert config.DB_NAME == "quantifiedstrides"

    def test_missing_required_var_raises(self):
        from pathlib import Path
        env = {k: v for k, v in os.environ.items() if k != "GARMIN_EMAIL"}
        env.pop("GARMIN_EMAIL", None)
        with patch.dict(os.environ, env, clear=True):
            with patch.object(Path, "exists", return_value=False):
                import importlib
                import config as cfg
                with pytest.raises(EnvironmentError, match="GARMIN_EMAIL"):
                    importlib.reload(cfg)

    def test_db_host_override(self):
        with patch.dict(os.environ, {"DB_HOST": "myserver"}):
            import importlib, config as cfg
            importlib.reload(cfg)
            assert cfg.DB_HOST == "myserver"
