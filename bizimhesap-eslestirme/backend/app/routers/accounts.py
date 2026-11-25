from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app import models as m

router = APIRouter(tags=["Banka Hesapları"])

@router.get("/bank-accounts")
def list_accounts(db: Session = Depends(get_db)):
    return [{"id": a.id, "name": a.name, "iban": a.iban, "currency": a.currency}
            for a in db.query(m.BankAccount).all()]
