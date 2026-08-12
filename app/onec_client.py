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

    def fetch_rows(self, base: OneCBaseConfig, start_date: date, end_date: date) -> list:
        try:
            response = requests.get(
                base.url,
                params={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
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


def _format_period(start_date: date, end_date: date) -> str:
    return f"{start_date:%d.%m.%Y}–{end_date:%d.%m.%Y}"
