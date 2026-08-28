from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.models import Discrepancy, LedgerRow, ReconciliationResult


MISSING_IN_TAX = "Отсутствует в бухгалтерии"
EXTRA_IN_TAX = "Лишняя строка в бухгалтерии"
DUPLICATE_IN_TAX = "Дублирующая строка в бухгалтерии"
DATA_MISMATCH = "Различия в остатках/оборотах"
AMBIGUOUS_MATCH = "Невозможность однозначного сопоставления"

RELOAD_DOCUMENT = "Догрузить строку в бухгалтерию"
REMOVE_DOCUMENT = "Проверить и удалить дубль либо лишнюю строку"
CHECK_DOCUMENT = "Проверить количество и стоимость"
MANUAL_CHECK = "Выполнить ручную проверку"


def reconcile(
    trade_rows: list[LedgerRow],
    tax_exports: dict[str, list[LedgerRow]],
    period: str,
    amount_tolerance: Decimal = Decimal("0.01"),
) -> ReconciliationResult:
    discrepancies: list[Discrepancy] = []
    trade_index = _aggregate_rows(trade_rows)

    for tax_base_name, tax_rows in tax_exports.items():
        raw_tax_index = _index_rows(tax_rows)
        duplicate_tax_keys = {key for key, rows in raw_tax_index.items() if len(rows) > 1}

        for key in duplicate_tax_keys:
            for row in raw_tax_index[key]:
                discrepancies.append(_from_row(row, tax_base_name, DUPLICATE_IN_TAX, REMOVE_DOCUMENT))

        tax_index = _aggregate_rows(tax_rows)

        for key, trade_row in trade_index.items():
            if key in duplicate_tax_keys:
                continue
            tax_row = tax_index.get(key)
            if tax_row is None:
                discrepancies.append(_from_row(trade_row, tax_base_name, MISSING_IN_TAX, RELOAD_DOCUMENT))
                continue
            if not _amounts_equal(trade_row, tax_row, amount_tolerance):
                discrepancies.append(_from_row(tax_row, tax_base_name, DATA_MISMATCH, CHECK_DOCUMENT))

        for key, tax_row in tax_index.items():
            if key in duplicate_tax_keys:
                continue
            if key not in trade_index:
                discrepancies.append(_from_row(tax_row, tax_base_name, EXTRA_IN_TAX, REMOVE_DOCUMENT))

    if not discrepancies and not tax_exports:
        discrepancies.append(
            Discrepancy(
                period=period,
                base="",
                document="",
                nomenclature="",
                opening_quantity=Decimal("0.00"),
                opening_amount=Decimal("0.00"),
                turnover_quantity=Decimal("0.00"),
                turnover_amount=Decimal("0.00"),
                closing_quantity=Decimal("0.00"),
                closing_amount=Decimal("0.00"),
                discrepancy_type=AMBIGUOUS_MATCH,
                recommendation="Не настроены базы бухгалтерии для сверки",
            )
        )

    return ReconciliationResult(discrepancies=discrepancies)


def _index_rows(rows: list[LedgerRow]) -> dict[tuple[str, str, str], list[LedgerRow]]:
    result: dict[tuple[str, str, str], list[LedgerRow]] = defaultdict(list)
    for row in rows:
        result[row.match_key].append(row)
    return result


def _aggregate_rows(rows: list[LedgerRow]) -> dict[tuple[str, str, str], LedgerRow]:
    return {
        key: _sum_rows(group)
        for key, group in _index_rows(rows).items()
    }


def _sum_rows(rows: list[LedgerRow]) -> LedgerRow:
    first = rows[0]
    return LedgerRow(
        period=first.period,
        document=first.document,
        nomenclature=first.nomenclature,
        opening_quantity=sum((row.opening_quantity for row in rows), Decimal("0.00")),
        opening_amount=sum((row.opening_amount for row in rows), Decimal("0.00")),
        turnover_quantity=sum((row.turnover_quantity for row in rows), Decimal("0.00")),
        turnover_amount=sum((row.turnover_amount for row in rows), Decimal("0.00")),
        closing_quantity=sum((row.closing_quantity for row in rows), Decimal("0.00")),
        closing_amount=sum((row.closing_amount for row in rows), Decimal("0.00")),
    )


def _amounts_equal(left: LedgerRow, right: LedgerRow, tolerance: Decimal) -> bool:
    return (
        abs(left.opening_quantity - right.opening_quantity) <= tolerance
        and abs(left.opening_amount - right.opening_amount) <= tolerance
        and abs(left.turnover_quantity - right.turnover_quantity) <= tolerance
        and abs(left.turnover_amount - right.turnover_amount) <= tolerance
        and abs(left.closing_quantity - right.closing_quantity) <= tolerance
        and abs(left.closing_amount - right.closing_amount) <= tolerance
    )


def _from_row(row: LedgerRow, base: str, discrepancy_type: str, recommendation: str) -> Discrepancy:
    return Discrepancy(
        period=row.period,
        base=base,
        document=row.document,
        nomenclature=row.nomenclature,
        opening_quantity=row.opening_quantity,
        opening_amount=row.opening_amount,
        turnover_quantity=row.turnover_quantity,
        turnover_amount=row.turnover_amount,
        closing_quantity=row.closing_quantity,
        closing_amount=row.closing_amount,
        discrepancy_type=discrepancy_type,
        recommendation=recommendation,
    )
