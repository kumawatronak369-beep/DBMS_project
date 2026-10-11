"""Collector settings, read from environment variables or collector/.env."""

import ipaddress
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

ENV_FILE = Path(__file__).with_name(".env")

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"  # 127.0.0.1 avoids a ~2s IPv6 fallback on Windows


class ConfigError(ValueError):
    pass


def load_env_file(path: Path = ENV_FILE, environ=None) -> None:
    environ = os.environ if environ is None else environ
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        environ.setdefault(key.strip(), value)


@dataclass(frozen=True)
class Settings:
    backend_url: str = DEFAULT_BACKEND_URL
    api_key: str = field(default="", repr=False)  # repr=False so the key never shows up in logs
    profile: str = "lab-a"
    interval: float = 2.0
    count: int = 0
    duplicate_rate: float = 0.15
    timeout: float = 5.0
    max_consecutive_errors: int = 10
    seed: int | None = None
    device_id: str = ""
    device_ip: str = ""

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def with_overrides(self, **values) -> "Settings":
        return validate(replace(self, **{k: v for k, v in values.items() if v is not None}))


def _number(environ, name, default, cast):
    raw = environ.get(name)
    if raw in (None, ""):
        return default
    try:
        return cast(raw)
    except ValueError:
        kind = "whole number" if cast is int else "number"
        raise ConfigError(f"{name} must be a {kind}") from None


def validate(settings: Settings) -> Settings:
    if not settings.backend_url.startswith(("http://", "https://")):
        raise ConfigError("COLLECTOR_BACKEND_URL must start with http:// or https://")
    if settings.interval < 0:
        raise ConfigError("COLLECTOR_INTERVAL must not be negative")
    if settings.count < 0:
        raise ConfigError("COLLECTOR_COUNT must not be negative (0 means run until stopped)")
    if not 0 <= settings.duplicate_rate <= 1:
        raise ConfigError("COLLECTOR_DUPLICATE_RATE must be between 0 and 1")
    if settings.timeout <= 0:
        raise ConfigError("COLLECTOR_TIMEOUT must be greater than 0")
    if settings.max_consecutive_errors < 1:
        raise ConfigError("COLLECTOR_MAX_ERRORS must be at least 1")
    if len(settings.device_id) > 100:
        raise ConfigError("COLLECTOR_DEVICE_ID must be at most 100 characters")
    if settings.device_ip:
        try:
            ipaddress.ip_address(settings.device_ip)
        except ValueError:
            raise ConfigError("COLLECTOR_DEVICE_IP must be a valid IP address") from None
    return settings


def from_env(environ=None) -> Settings:
    environ = os.environ if environ is None else environ
    settings = Settings(
        backend_url=(environ.get("COLLECTOR_BACKEND_URL") or DEFAULT_BACKEND_URL).rstrip("/"),
        api_key=(environ.get("COLLECTOR_API_KEY") or "").strip(),
        profile=(environ.get("COLLECTOR_PROFILE") or "lab-a").strip().lower(),
        interval=_number(environ, "COLLECTOR_INTERVAL", 2.0, float),
        count=_number(environ, "COLLECTOR_COUNT", 0, int),
        duplicate_rate=_number(environ, "COLLECTOR_DUPLICATE_RATE", 0.15, float),
        timeout=_number(environ, "COLLECTOR_TIMEOUT", 5.0, float),
        max_consecutive_errors=_number(environ, "COLLECTOR_MAX_ERRORS", 10, int),
        seed=_number(environ, "COLLECTOR_SEED", None, int),
        device_id=(environ.get("COLLECTOR_DEVICE_ID") or "").strip(),
        device_ip=(environ.get("COLLECTOR_DEVICE_IP") or "").strip(),
    )
    return validate(settings)


def load_settings() -> Settings:
    load_env_file()
    return from_env()
