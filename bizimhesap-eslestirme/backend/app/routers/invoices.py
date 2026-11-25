from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.session import get_db
from app import models as m
from app.services import import_service as imp
from app.services.errors import BusinessError

router = APIRouter(tags=["Faturalar"])

class InvoiceIn(BaseModel):
    invoice_no: str = Field(min_length=1, max_length=40)
    kind: str = Field(pattern="^(SALE|PURCH)$")
    party_name: str = Field(min_length=1)
    issue_date: date; due_date: date
    total: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = "TRY"
    doc_type: str = "Faturalaşmış"

def _out(i):
    return {"id": i.id, "invoice_no": i.invoice_no, "kind": i.kind, "doc_type": i.doc_type, "party": i.party_name,
            "total_kurus": i.total_kurus, "paid_kurus": i.paid_kurus, "remaining_kurus": i.remaining_kurus,
            "currency": i.currency, "status": i.payment_status, "issue_date": i.issue_date.isoformat(),
            "due_date": i.due_date.isoformat()}

@router.get("/invoices")
def list_inv(kind: str | None = None, doc_type: str | None = None, status: str | None = None, q: str | None = None,
             db: Session = Depends(get_db)):
    rows = [i for i in db.query(m.Invoice).order_by(m.Invoice.issue_date, m.Invoice.id)
            if (not kind or i.kind == kind) and (not doc_type or i.doc_type == doc_type)
            and (not status or i.payment_status == status) and (not q or q.lower() in i.invoice_no.lower())]
    return [_out(i) for i in rows]

@router.post("/invoices", status_code=201)
def create_inv(body: InvoiceIn, db: Session = Depends(get_db)):
    row = {"fatura_no": body.invoice_no, "tur": body.kind, "cari_unvan": body.party_name,
           "fatura_tarihi": body.issue_date.isoformat(), "vade_tarihi": body.due_date.isoformat(),
           "tutar": str(body.total), "para_birimi": body.currency, "belge_tipi": body.doc_type}
    try: inv = imp.make_invoice(db, row, set())
    except ValueError as e: raise BusinessError(str(e))
    if inv is None: raise BusinessError("Bu fatura numarası zaten kayıtlı.", 409)
    db.commit(); return _out(inv)

@router.post("/invoices/import")
async def import_inv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    df = imp.read_table(file.filename, await file.read(), imp.INV_COLS)
    return imp.import_rows(db, df, imp.make_invoice)
