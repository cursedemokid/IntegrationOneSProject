from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LedgerRow:
    period: str
    document: str
    nomenclature: str
    opening_quantity: Decimal
    opening_amount: Decimal
    turnover_quantity: Decimal
    turnover_amount: Decimal
    closing_quantity: Decimal
    closing_amount: Decimal

    @property
    def match_key(self) -> tuple[str, str, str]:
        return (
            self.period,
            self.document,
            self.nomenclature,
        )


@dataclass(frozen=True)
class Discrepancy:
    period: str
    base: str
    document: str
    nomenclature: str
    opening_quantity: Decimal
    opening_amount: Decimal
    turnover_quantity: Decimal
    turnover_amount: Decimal
    closing_quantity: Decimal
    closing_amount: Decimal
    discrepancy_type: str
    recommendation: str


@dataclass(frozen=True)
class ReconciliationResult:
    discrepancies: list[Discrepancy]
