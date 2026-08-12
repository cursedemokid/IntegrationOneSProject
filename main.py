import logging
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field, model_validator

from app.config import ConfigurationError, load_settings
from app.onec_client import OneCClient, OneCClientError
from app.reconciliation import reconcile
from app.reporting import build_excel_report


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Сверка остатков 1С")


class ReconcileRequest(BaseModel):
    start_date: date = Field(..., description="Начальная дата периода включительно")
    end_date: date = Field(..., description="Конечная дата периода включительно")

    @model_validator(mode="after")
    def validate_date_range(self) -> "ReconcileRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date должен быть больше или равен start_date")
        return self


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    with open("index.html", "r", encoding="utf-8") as file:
        return HTMLResponse(file.read())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/reconcile")
async def run_reconciliation(payload: ReconcileRequest) -> Response:
    logger.info(
        "Reconciliation started: start_date=%s end_date=%s",
        payload.start_date,
        payload.end_date,
    )
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        logger.exception("Reconciliation configuration error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    client = OneCClient(timeout_seconds=settings.timeout_seconds)

    try:
        trade_rows = client.fetch_rows(
            settings.trade_base,
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
        tax_exports = {
            tax_base.name: client.fetch_rows(
                tax_base,
                start_date=payload.start_date,
                end_date=payload.end_date,
            )
            for tax_base in settings.tax_bases
        }
    except OneCClientError as exc:
        logger.exception("Reconciliation data loading error")
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    period = _format_period(payload.start_date, payload.end_date)
    result = reconcile(
        trade_rows=trade_rows,
        tax_exports=tax_exports,
        period=period,
        amount_tolerance=settings.amount_tolerance,
    )
    logger.info(
        "Reconciliation completed: start_date=%s end_date=%s trade_rows=%s tax_bases=%s discrepancies=%s",
        payload.start_date,
        payload.end_date,
        len(trade_rows),
        len(tax_exports),
        len(result.discrepancies),
    )
    content = build_excel_report(result.discrepancies)
    filename = f"reconciliation_{payload.start_date.isoformat()}_{payload.end_date.isoformat()}.xlsx"

    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _format_period(start_date: date, end_date: date) -> str:
    return f"{start_date:%d.%m.%Y}–{end_date:%d.%m.%Y}"
