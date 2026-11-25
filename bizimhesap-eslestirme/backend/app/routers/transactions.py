from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.session import get_db
from app import models as m
from app.services import import_service as imp, reconciliation_service as svc
from app.services.errors import BusinessError

router = APIRouter(tags=["Banka Hareketleri"])

class TxIn(BaseModel):
    account_id: int
    date: date
    direction: str = Field(pattern="^(IN|OUT)$")       # açık işlem yönü
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    category: str = "PAYMENT"

def _out(t):
    return {"id": t.id, "account_id": t.account_id, "date": t.tx_date.isoformat(), "direction": t.direction,
            "category": t.category, "description": t.description, "amount_kurus": t.amount_kurus,
            "currency": t.currency, "status": t.status}

@router.get("/bank-transactions")
def list_tx(status: str | None = None, q: str | None = Query(None), direction: str | None = None,
            date_from: date | None = None, date_to: date | None = None, account_id: int | None = None,
            db: Session = Depends(get_db)):
    qs = db.query(m.BankTransaction)
    if status: qs = qs.filter(m.BankTransaction.status == status)
    if direction: qs = qs.filter(m.BankTransaction.direction == direction)
    if account_id: qs = qs.filter(m.BankTransaction.account_id == account_id)
    if date_from: qs = qs.filter(m.BankTransaction.tx_date >= date_from)
    if date_to: qs = qs.filter(m.BankTransaction.tx_date <= date_to)
    if q: qs = qs.filter(m.BankTransaction.description.ilike(f"%{q}%"))
    return [_out(t) for t in qs.order_by(m.BankTransaction.tx_date, m.BankTransaction.id).all()]

@router.get("/bank-transactions/{tx_id}")
def tx_detail(tx_id: int, db: Session = Depends(get_db)):
    t = db.get(m.BankTransaction, tx_id)
    if not t: raise BusinessError("Banka hareketi bulunamadı.", 404)
    return _out(t)

@router.post("/bank-transactions", status_code=201)
def create_tx(body: TxIn, db: Session = Depends(get_db)):
    acc = db.get(m.BankAccount, body.account_id)
    if not acc: raise BusinessError("Banka hesabı bulunamadı.", 404)
    row = {"hesap_iban": acc.iban, "tarih": body.date.isoformat(), "yon": body.direction, "tutar": str(body.amount),
           "para_birimi": acc.currency, "aciklama": body.description, "kategori": body.category}
    try: t = imp.make_transaction(db, row, set())
    except ValueError as e: raise BusinessError(str(e))
    if t is None: raise BusinessError("Bu banka hareketi daha önce kaydedilmiş (mükerrer).", 409)
    db.commit(); svc.run(db, "event", [t.id]); db.refresh(t)
    return _out(t)

@router.post("/bank-transactions/import")
async def import_tx(file: UploadFile = File(...), db: Session = Depends(get_db)):
    df = imp.read_table(file.filename, await file.read(), imp.TX_COLS)
    res = imp.import_rows(db, df, imp.make_transaction)
    if res["ids"]: svc.run(db, "event", res["ids"])     # olay tabanlı otomasyon
    return res
