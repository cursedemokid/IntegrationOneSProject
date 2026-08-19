from __future__ import annotations

import json
import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


class ConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OneCBaseConfig:
    name: str
    url: str
    warehouses_url: str | None = None
    username: str | None = None
    password: str | None = None


@dataclass(frozen=True)
class Settings:
    trade_base: OneCBaseConfig
    tax_bases: list[OneCBaseConfig]
    timeout_seconds: float = 15.0
    amount_tolerance: Decimal = Decimal("0.01")


def load_settings(env_file: str = ".env") -> Settings:
    values = _load_env_file(env_file) | dict(os.environ)

    trade_base = OneCBaseConfig(
        name=values.get("ONEC_TRADE_NAME", "Управление торговлей"),
        url=_required(values, "ONEC_TRADE_URL"),
        warehouses_url=values.get("ONEC_TRADE_WAREHOUSES_URL"),
        username=values.get("ONEC_TRADE_USERNAME"),
        password=values.get("ONEC_TRADE_PASSWORD"),
    )

    tax_bases_raw = _required(values, "ONEC_TAX_BASES_JSON")
    try:
        tax_bases_payload = json.loads(tax_bases_raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError("ONEC_TAX_BASES_JSON должен быть валидным JSON") from exc

    if not isinstance(tax_bases_payload, list) or not tax_bases_payload:
        raise ConfigurationError("ONEC_TAX_BASES_JSON должен содержать непустой список баз")

    tax_bases = [_parse_base_config(item, index) for index, item in enumerate(tax_bases_payload, start=1)]

    return Settings(
        trade_base=trade_base,
        tax_bases=tax_bases,
        timeout_seconds=float(values.get("ONEC_HTTP_TIMEOUT_SECONDS", "15")),
        amount_tolerance=Decimal(values.get("ONEC_AMOUNT_TOLERANCE", "0.01")),
    )


def _load_env_file(env_file: str) -> dict[str, str]:
    path = Path(env_file)
    if not path.exists():
        return {}

    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _required(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if not value:
        raise ConfigurationError(f"Не задан обязательный параметр конфигурации {key}")
    return value


def _parse_base_config(item: Any, index: int) -> OneCBaseConfig:
    if not isinstance(item, dict):
        raise ConfigurationError(f"Налоговая база #{index} должна быть объектом")
    name = item.get("name") or f"Налоговая база {index}"
    url = item.get("url")
    if not url:
        raise ConfigurationError(f"Для налоговой базы {name} не задан url")
    return OneCBaseConfig(
        name=str(name),
        url=str(url),
        warehouses_url=item.get("warehouses_url"),
        username=item.get("username"),
        password=item.get("password"),
    )
