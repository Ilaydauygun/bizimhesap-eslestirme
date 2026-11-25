from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database.session import get_db
from app import models as m

router = APIRouter(tags=["Dashboard"])

@router.get("/dashboard/stats")
def stats(db: Session = Depends(get_db)):
    total = db.query(func.count(m.BankTransaction.id)).scalar()
    by = dict(db.query(m.BankTransaction.status, func.count()).group_by(m.BankTransaction.status).all())
    matched = by.get("MATCHED", 0)
    return {"total": total, "matched": matched, "pending": by.get("PENDING", 0),
            "unmatched": by.get("UNMATCHED", 0), "partial": db.query(func.count(m.Invoice.id)).filter(m.Invoice.paid_kurus > 0, m.Invoice.paid_kurus < m.Invoice.total_kurus).scalar(),
            "match_rate": round(matched / total * 100, 1) if total else 0.0}
