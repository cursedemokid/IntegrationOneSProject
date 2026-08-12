from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class LedgerRow:
    period: str
    document: str
    debit_analytics: str
    credit_analytics: str
    debit: Decimal
    credit: Decimal
    balance: Decimal

    @property
    def match_key(self) -> tuple[str, str, str, str]:
        return (
            self.period,
            self.document,
            self.debit_analytics,
            self.credit_analytics,
        )


@dataclass(frozen=True)
class Discrepancy:
    period: str
    base: str
    document: str
    debit_analytics: str
    credit_analytics: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    discrepancy_type: str
    recommendation: str


@dataclass(frozen=True)
class ReconciliationResult:
    discrepancies: list[Discrepancy]
