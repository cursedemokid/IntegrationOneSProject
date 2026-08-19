from __future__ import annotations

from datetime import date
from typing import Any

import requests

from app.config import OneCBaseConfig
from app.normalization import NormalizationError, normalize_rows


class OneCClientError(RuntimeError):
    pass


class OneCClient:
    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_rows(
        self,
        base: OneCBaseConfig,
        start_date: date,
        end_date: date,
        warehouses: list[str] | None = None,
    ) -> list:
        try:
            response = requests.get(
                base.url,
                params=_build_reconciliation_params(start_date, end_date, warehouses),
                auth=(base.username, base.password) if base.username or base.password else None,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except requests.RequestException as exc:
            raise OneCClientError(f"Не удалось получить данные из базы «{base.name}»: {exc}") from exc
        except ValueError as exc:
            raise OneCClientError(f"База «{base.name}» вернула некорректный JSON") from exc

        try:
            return normalize_rows(payload, default_period=_format_period(start_date, end_date))
        except NormalizationError as exc:
            raise OneCClientError(f"Некорректные данные из базы «{base.name}»: {exc}") from exc

    def fetch_warehouses(self, base: OneCBaseConfig) -> list[str]:
        if not base.warehouses_url:
            raise OneCClientError("Не задан ONEC_TRADE_WAREHOUSES_URL для получения списка складов")

        try:
            response = requests.get(
                base.warehouses_url,
                auth=(base.username, base.password) if base.username or base.password else None,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload: Any = response.json()
        except requests.RequestException as exc:
            raise OneCClientError(f"Не удалось получить список складов из базы «{base.name}»: {exc}") from exc
        except ValueError as exc:
            raise OneCClientError(f"База «{base.name}» вернула некорректный JSON со списком складов") from exc

        try:
            return normalize_warehouses(payload)
        except ValueError as exc:
            raise OneCClientError(f"Некорректный список складов из базы «{base.name}»: {exc}") from exc


def normalize_warehouses(payload: Any) -> list[str]:
    records = _extract_warehouse_records(payload)
    result: list[str] = []
    seen: set[str] = set()

    for record in records:
        name = _extract_warehouse_name(record)
        normalized = " ".join(name.strip().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def _extract_warehouse_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("warehouses", "data", "items", "rows", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("ответ должен быть списком складов или объектом с warehouses/data/items/rows/result")


def _extract_warehouse_name(record: Any) -> str:
    if isinstance(record, str):
        return record
    if isinstance(record, dict):
        for key in ("name", "Название", "название", "Склад", "склад", "warehouse"):
            value = record.get(key)
            if value is not None:
                return str(value)
    raise ValueError("строка склада должна быть строкой или объектом с name/Название/Склад")


def _build_reconciliation_params(
    start_date: date,
    end_date: date,
    warehouses: list[str] | None = None,
) -> list[tuple[str, str]]:
    params = [
        ("start_date", start_date.isoformat()),
        ("end_date", end_date.isoformat()),
    ]
    for warehouse in warehouses or []:
        normalized = " ".join(str(warehouse).strip().split())
        if normalized:
            params.append(("warehouse", normalized))
    return params


def _format_period(start_date: date, end_date: date) -> str:
    return f"{start_date:%d.%m.%Y}–{end_date:%d.%m.%Y}"
