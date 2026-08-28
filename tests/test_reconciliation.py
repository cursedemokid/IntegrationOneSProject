import base64
from datetime import date
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock, patch

from app.config import OneCBaseConfig
from app.models import LedgerRow
from app.normalization import normalize_row
from app.onec_client import OneCClient, normalize_warehouses
from app.reconciliation import (
    DATA_MISMATCH,
    DUPLICATE_IN_TAX,
    EXTRA_IN_TAX,
    MISSING_IN_TAX,
    reconcile,
)
from app.reporting import build_excel_report
from main import ReconcileRequest, _format_period


def row(
    nomenclature: str,
    document: str = "",
    period: str = "01.08.2026 0:00:00",
    opening_quantity: str = "10.00",
    opening_amount: str = "100.00",
    turnover_quantity: str = "0.00",
    turnover_amount: str = "0.00",
    closing_quantity: str = "10.00",
    closing_amount: str = "100.00",
) -> LedgerRow:
    return LedgerRow(
        period=period,
        document=document,
        nomenclature=nomenclature,
        opening_quantity=Decimal(opening_quantity),
        opening_amount=Decimal(opening_amount),
        turnover_quantity=Decimal(turnover_quantity),
        turnover_amount=Decimal(turnover_amount),
        closing_quantity=Decimal(closing_quantity),
        closing_amount=Decimal(closing_amount),
    )


class NormalizationTests(TestCase):
    def test_normalizes_stock_turnover_fields_and_amounts(self) -> None:
        normalized = normalize_row(
            {
                "Период": " 01.08.2026 0:00:00 ",
                "Документ": "",
                "Номенклатура": "  Товар  1 ",
                "КоличествоНачальныйОстаток": "1 000,005",
                "СтоимостьНачальныйОстаток": "2 000,004",
                "КоличествоОборот": "-10",
                "СтоимостьОборот": "-20,1",
                "КоличествоКонечныйОстаток": "990,005",
                "СтоимостьКонечныйОстаток": "1 979,904",
            },
            default_period="I 2024",
        )

        self.assertEqual(normalized.document, "")
        self.assertEqual(normalized.nomenclature, "Товар 1")
        self.assertEqual(normalized.opening_quantity, Decimal("1000.01"))
        self.assertEqual(normalized.opening_amount, Decimal("2000.00"))
        self.assertEqual(normalized.closing_amount, Decimal("1979.90"))


class RequestValidationTests(TestCase):
    def test_accepts_valid_date_range(self) -> None:
        payload = ReconcileRequest(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

        self.assertEqual(payload.start_date, date(2024, 1, 1))
        self.assertEqual(payload.end_date, date(2024, 1, 31))

    def test_normalizes_warehouses(self) -> None:
        payload = ReconcileRequest(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            warehouses=[" Основной  склад ", "", "Склад 2", "Основной склад"],
        )

        self.assertEqual(payload.warehouses, ["Основной склад", "Склад 2"])

    def test_rejects_end_date_before_start_date(self) -> None:
        with self.assertRaises(ValueError):
            ReconcileRequest(start_date=date(2024, 2, 1), end_date=date(2024, 1, 31))

    def test_formats_period_as_inclusive_date_range(self) -> None:
        self.assertEqual(
            _format_period(date(2024, 1, 1), date(2024, 1, 31)),
            "01.01.2024–31.01.2024",
        )


class OneCClientTests(TestCase):
    @patch("app.onec_client.requests.get")
    def test_sends_start_and_end_date_params(self, mocked_get: Mock) -> None:
        response = Mock()
        response.json.return_value = []
        response.raise_for_status.return_value = None
        mocked_get.return_value = response

        client = OneCClient(timeout_seconds=3)
        client.fetch_rows(
            OneCBaseConfig(name="Налоговая", url="https://example.test/export"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        mocked_get.assert_called_once()
        self.assertEqual(
            mocked_get.call_args.kwargs["params"],
            [("start_date", "2024-01-01"), ("end_date", "2024-01-31")],
        )

    @patch("app.onec_client.requests.get")
    def test_sends_repeated_warehouse_params(self, mocked_get: Mock) -> None:
        response = Mock()
        response.json.return_value = []
        response.raise_for_status.return_value = None
        mocked_get.return_value = response

        client = OneCClient(timeout_seconds=3)
        client.fetch_rows(
            OneCBaseConfig(name="Налоговая", url="https://example.test/export"),
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            warehouses=[" Основной  склад ", "Склад 2"],
        )

        self.assertEqual(
            mocked_get.call_args.kwargs["params"],
            [
                ("start_date", "2024-01-01"),
                ("end_date", "2024-01-31"),
                ("warehouse", "Основной склад"),
                ("warehouse", "Склад 2"),
            ],
        )

    @patch("app.onec_client.requests.post")
    def test_sends_postman_json_period_payload(self, mocked_post: Mock) -> None:
        response = Mock()
        response.json.return_value = []
        response.raise_for_status.return_value = None
        mocked_post.return_value = response

        client = OneCClient(timeout_seconds=3)
        client.fetch_rows(
            OneCBaseConfig(
                name="Trade",
                url="https://example.test/stocksturnover",
                username="user",
                password="password",
                request_method="POST",
                date_format="%Y%m%d",
                period_begin_key="periodBegin",
                period_end_key="periodEnd",
            ),
            start_date=date(2026, 1, 24),
            end_date=date(2026, 1, 31),
        )

        mocked_post.assert_called_once()
        self.assertEqual(
            mocked_post.call_args.kwargs["json"],
            {"periodBegin": "20260124", "periodEnd": "20260131"},
        )
        expected_token = base64.b64encode("user:password".encode("utf-8")).decode("ascii")
        self.assertEqual(mocked_post.call_args.kwargs["headers"], {"Authorization": f"Basic {expected_token}"})

    def test_normalizes_warehouse_string_list(self) -> None:
        self.assertEqual(
            normalize_warehouses([" Основной  склад ", "", "Склад 2", "Основной склад"]),
            ["Основной склад", "Склад 2"],
        )

    def test_normalizes_warehouse_object_list(self) -> None:
        self.assertEqual(
            normalize_warehouses(
                {
                    "data": [
                        {"name": "Основной склад"},
                        {"Название": "Склад 2"},
                        {"Склад": "Склад 3"},
                    ]
                }
            ),
            ["Основной склад", "Склад 2", "Склад 3"],
        )


class ReconciliationTests(TestCase):
    def test_no_discrepancies_within_tolerance(self) -> None:
        result = reconcile(
            trade_rows=[row("Товар 1", opening_amount="100.00")],
            tax_exports={"Бухгалтерия": [row("Товар 1", opening_amount="100.01")]},
            period="I 2024",
            amount_tolerance=Decimal("0.01"),
        )

        self.assertEqual(result.discrepancies, [])

    def test_detects_missing_document_in_tax_base(self) -> None:
        result = reconcile(
            trade_rows=[row("Товар 1")],
            tax_exports={"Бухгалтерия": []},
            period="I 2024",
        )

        self.assertEqual(result.discrepancies[0].discrepancy_type, MISSING_IN_TAX)

    def test_detects_extra_document_in_tax_base(self) -> None:
        result = reconcile(
            trade_rows=[],
            tax_exports={"Бухгалтерия": [row("Товар 1")]},
            period="I 2024",
        )

        self.assertEqual(result.discrepancies[0].discrepancy_type, EXTRA_IN_TAX)

    def test_detects_duplicate_document_in_tax_base(self) -> None:
        result = reconcile(
            trade_rows=[row("Товар 1")],
            tax_exports={"Бухгалтерия": [row("Товар 1"), row("Товар 1")]},
            period="I 2024",
        )

        self.assertTrue(any(item.discrepancy_type == DUPLICATE_IN_TAX for item in result.discrepancies))
        self.assertFalse(any(item.discrepancy_type == MISSING_IN_TAX for item in result.discrepancies))

    def test_detects_amount_mismatch(self) -> None:
        result = reconcile(
            trade_rows=[row("Товар 1", closing_amount="100.00")],
            tax_exports={"Бухгалтерия": [row("Товар 1", closing_amount="100.02")]},
            period="I 2024",
            amount_tolerance=Decimal("0.01"),
        )

        self.assertEqual(result.discrepancies[0].discrepancy_type, DATA_MISMATCH)

    def test_aggregates_trade_rows_as_source_of_truth(self) -> None:
        result = reconcile(
            trade_rows=[
                row("Товар 1", opening_quantity="2.00", opening_amount="20.00", closing_quantity="2.00", closing_amount="20.00"),
                row("Товар 1", opening_quantity="3.00", opening_amount="30.00", closing_quantity="3.00", closing_amount="30.00"),
            ],
            tax_exports={
                "Бухгалтерия": [
                    row("Товар 1", opening_quantity="5.00", opening_amount="50.00", closing_quantity="5.00", closing_amount="50.00")
                ]
            },
            period="I 2024",
        )

        self.assertEqual(result.discrepancies, [])


class ReportingTests(TestCase):
    def test_builds_xlsx_bytes(self) -> None:
        content = build_excel_report([])

        self.assertTrue(content.startswith(b"PK"))
        self.assertIn(b"[Content_Types].xml", content)
