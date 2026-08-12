from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.models import Discrepancy, LedgerRow, ReconciliationResult


MISSING_IN_TAX = "Отсутствие документа в налоговой базе"
EXTRA_IN_TAX = "Лишний документ в налоговой базе"
DUPLICATE_IN_TAX = "Дублирующий документ"
DATA_MISMATCH = "Различия в данных документа"
AMBIGUOUS_MATCH = "Невозможность однозначного сопоставления"

RELOAD_DOCUMENT = "Догрузить документ в налоговую базу"
REMOVE_DOCUMENT = "Проверить и удалить документ либо отменить его проведение"
CHECK_DOCUMENT = "Проверить корректность документа"
MANUAL_CHECK = "Выполнить ручную проверку"


def reconcile(
    trade_rows: list[LedgerRow],
    tax_exports: dict[str, list[LedgerRow]],
    period: str,
    amount_tolerance: Decimal = Decimal("0.01"),
) -> ReconciliationResult:
    discrepancies: list[Discrepancy] = []
    trade_index = _index_rows(trade_rows)

    ambiguous_trade_keys = {key for key, rows in trade_index.items() if len(rows) > 1}
    for key in ambiguous_trade_keys:
        for row in trade_index[key]:
            discrepancies.append(_from_row(row, "Управление торговлей", AMBIGUOUS_MATCH, MANUAL_CHECK))

    comparable_trade_index = {
        key: rows[0]
        for key, rows in trade_index.items()
        if key not in ambiguous_trade_keys
    }

    for tax_base_name, tax_rows in tax_exports.items():
        tax_index = _index_rows(tax_rows)
        duplicate_tax_keys = {key for key, rows in tax_index.items() if len(rows) > 1}

        for key in duplicate_tax_keys:
            for row in tax_index[key]:
                discrepancies.append(_from_row(row, tax_base_name, DUPLICATE_IN_TAX, REMOVE_DOCUMENT))

        comparable_tax_index = {
            key: rows[0]
            for key, rows in tax_index.items()
            if key not in duplicate_tax_keys
        }

        for key, trade_row in comparable_trade_index.items():
            if key in duplicate_tax_keys:
                continue
            tax_row = comparable_tax_index.get(key)
            if tax_row is None:
                discrepancies.append(_from_row(trade_row, tax_base_name, MISSING_IN_TAX, RELOAD_DOCUMENT))
                continue
            if not _amounts_equal(trade_row, tax_row, amount_tolerance):
                discrepancies.append(_from_row(tax_row, tax_base_name, DATA_MISMATCH, CHECK_DOCUMENT))

        for key, tax_row in comparable_tax_index.items():
            if key in ambiguous_trade_keys:
                continue
            if key not in comparable_trade_index:
                discrepancies.append(_from_row(tax_row, tax_base_name, EXTRA_IN_TAX, REMOVE_DOCUMENT))

    if not discrepancies and not tax_exports:
        discrepancies.append(
            Discrepancy(
                period=period,
                base="",
                document="",
                debit_analytics="",
                credit_analytics="",
                debit=Decimal("0.00"),
                credit=Decimal("0.00"),
                balance=Decimal("0.00"),
                discrepancy_type=AMBIGUOUS_MATCH,
                recommendation="Не настроены налоговые базы для сверки",
            )
        )

    return ReconciliationResult(discrepancies=discrepancies)


def _index_rows(rows: list[LedgerRow]) -> dict[tuple[str, str, str, str], list[LedgerRow]]:
    result: dict[tuple[str, str, str, str], list[LedgerRow]] = defaultdict(list)
    for row in rows:
        result[row.match_key].append(row)
    return result


def _amounts_equal(left: LedgerRow, right: LedgerRow, tolerance: Decimal) -> bool:
    return (
        abs(left.debit - right.debit) <= tolerance
        and abs(left.credit - right.credit) <= tolerance
        and abs(left.balance - right.balance) <= tolerance
    )


def _from_row(row: LedgerRow, base: str, discrepancy_type: str, recommendation: str) -> Discrepancy:
    return Discrepancy(
        period=row.period,
        base=base,
        document=row.document,
        debit_analytics=row.debit_analytics,
        credit_analytics=row.credit_analytics,
        debit=row.debit,
        credit=row.credit,
        balance=row.balance,
        discrepancy_type=discrepancy_type,
        recommendation=recommendation,
    )
