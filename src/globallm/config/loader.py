"""Configuration loader with YAML support and hot-reload."""

import signal
from pathlib import Path
from typing import Any, Callable

import yaml
from pydantic import ValidationError

from globallm.config.settings import Settings
from globallm.config.defaults import DEFAULT_CONFIG_DICT
from globallm.logging_config import get_logger

logger = get_logger(__name__)

# Global settings instance
_global_settings: Settings | None = None
_config_path: Path | None = None
_reload_callbacks: list[Callable[[Settings | None, Settings | None], None]] = []


def get_config_path() -> Path:
    """Get the default configuration file path."""
    config_dir = Path.home() / ".config" / "globallm"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.yaml"


def _merge_dicts(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _settings_from_dict(data: dict[str, Any] | None) -> Settings:
    """Create Settings from dict with defaults."""
    if data is None:
        return Settings(**DEFAULT_CONFIG_DICT)

    merged = _merge_dicts(DEFAULT_CONFIG_DICT, data)
    return Settings(**merged)


def load_config(path: Path | str | None = None) -> Settings:
    """Load configuration from YAML file.

    Args:
        path: Path to config file. If None, uses default path.

    Returns:
        Settings object with loaded configuration.
    """
    global _global_settings, _config_path

    if path is None:
        path = get_config_path()
    else:
        path = Path(path)

    _config_path = path

    if not path.exists():
        logger.info("config_not_found", path=str(path), using_defaults=True)
        _global_settings = Settings(**DEFAULT_CONFIG_DICT)
        _save_default_config(path)
        return _global_settings

    try:
        with path.open() as f:
            data = yaml.safe_load(f)
            if data is None:
                data = {}

        _global_settings = _settings_from_dict(data)
        logger.info("config_loaded", path=str(path))
        return _global_settings

    except yaml.YAMLError as e:
        logger.error("config_yaml_error", path=str(path), error=str(e))
        raise
    except ValidationError as e:
        logger.error("config_validation_error", path=str(path), error=str(e))
        raise
    except Exception as e:
        logger.error("config_load_error", path=str(path), error=str(e))
        raise


def _save_default_config(path: Path) -> None:
    """Save default configuration to file."""
    try:
        with path.open("w") as f:
            yaml.dump(DEFAULT_CONFIG_DICT, f, default_flow_style=False, sort_keys=False)
        logger.info("default_config_saved", path=str(path))
    except Exception as e:
        logger.warning("default_config_save_failed", path=str(path), error=str(e))


def save_config(settings: Settings, path: Path | str | None = None) -> None:
    """Save configuration to YAML file.

    Args:
        settings: Settings object to save.
        path: Path to save to. If None, uses path from last load or default.
    """
    global _config_path

    if path is None:
        path = _config_path or get_config_path()
    else:
        path = Path(path)

    _config_path = path

    try:
        with path.open("w") as f:
            yaml.dump(
                settings.model_dump(mode="json", exclude_none=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
        logger.info("config_saved", path=str(path))
    except Exception as e:
        logger.error("config_save_error", path=str(path), error=str(e))
        raise


def reload_config() -> Settings:
    """Reload configuration from file and notify callbacks."""
    global _global_settings, _config_path

    if _config_path is None:
        _config_path = get_config_path()

    old_settings = _global_settings
    _global_settings = load_config(_config_path)

    # Notify callbacks
    for callback in _reload_callbacks:
        try:
            callback(old_settings, _global_settings)
        except Exception as e:
            logger.warning("config_reload_callback_failed", error=str(e))

    logger.info("config_reloaded", path=str(_config_path))
    return _global_settings


def on_reload(callback: Callable[[Settings | None, Settings | None], None]) -> None:
    """Register a callback to be called on config reload.

    Args:
        callback: Function called with (old_settings, new_settings).
    """
    _reload_callbacks.append(callback)


def get_settings() -> Settings:
    """Get the current global settings instance.

    Loads from default path if not already loaded.
    """
    global _global_settings
    if _global_settings is None:
        _global_settings = load_config()
    return _global_settings


def setup_signal_reload() -> None:
    """Set up SIGHUP handler for config reload."""
    try:
        signal.signal(signal.SIGHUP, lambda sig, frame: reload_config())
        logger.info("config_signal_reload_enabled")
    except (ValueError, AttributeError) as e:
        # SIGHUP not available on this platform
        logger.debug("config_signal_reload_unavailable", error=str(e))


# Initialize on import
setup_signal_reload()
