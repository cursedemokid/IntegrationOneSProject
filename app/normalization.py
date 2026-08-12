from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from app.models import LedgerRow


class NormalizationError(ValueError):
    pass


FIELD_ALIASES = {
    "period": ("period", "Период", "период"),
    "document": ("document", "Документ", "документ"),
    "debit_analytics": ("debit_analytics", "Аналитика Дт", "аналитика дт", "Analytic Dt"),
    "credit_analytics": ("credit_analytics", "Аналитика Кт", "аналитика кт", "Analytic Kt"),
    "debit": ("debit", "Дебет", "дебет"),
    "credit": ("credit", "Кредит", "кредит"),
    "balance": ("balance", "Текущее сальдо", "текущее сальдо"),
}


def normalize_rows(payload: Any, default_period: str) -> list[LedgerRow]:
    records = _extract_records(payload)
    return [normalize_row(record, default_period) for record in records]


def normalize_row(record: dict[str, Any], default_period: str) -> LedgerRow:
    if not isinstance(record, dict):
        raise NormalizationError("Строка выгрузки должна быть объектом")

    period = _normalize_text(_get_value(record, "period") or default_period)
    document = _normalize_text(_required_value(record, "document"))
    debit_analytics = _normalize_text(_required_value(record, "debit_analytics"))
    credit_analytics = _normalize_text(_required_value(record, "credit_analytics"))

    if not period or not document or not debit_analytics or not credit_analytics:
        raise NormalizationError("Период, документ и аналитики не должны быть пустыми")

    return LedgerRow(
        period=period,
        document=document,
        debit_analytics=debit_analytics,
        credit_analytics=credit_analytics,
        debit=_normalize_amount(_required_value(record, "debit")),
        credit=_normalize_amount(_required_value(record, "credit")),
        balance=_normalize_amount(_required_value(record, "balance")),
    )


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "items", "rows", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise NormalizationError("Ответ 1С должен быть списком строк или объектом с data/items/rows/result")


def _required_value(record: dict[str, Any], canonical_name: str) -> Any:
    value = _get_value(record, canonical_name)
    if value is None:
        raise NormalizationError(f"Не найдено обязательное поле {canonical_name}")
    return value


def _get_value(record: dict[str, Any], canonical_name: str) -> Any:
    aliases = FIELD_ALIASES[canonical_name]
    lowered = {str(key).strip().lower(): value for key, value in record.items()}
    for alias in aliases:
        direct = record.get(alias)
        if direct is not None:
            return direct
        lowered_value = lowered.get(alias.lower())
        if lowered_value is not None:
            return lowered_value
    return None


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).strip().split())


def _normalize_amount(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        amount = value
    else:
        prepared = str(value).strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            amount = Decimal(prepared)
        except InvalidOperation as exc:
            raise NormalizationError(f"Некорректный формат суммы: {value}") from exc
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
