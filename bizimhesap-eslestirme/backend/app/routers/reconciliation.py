import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.session import get_db
from app import models as m
from app.services import reconciliation_service as svc
from app.services.errors import BusinessError

router = APIRouter(prefix="/reconciliation", tags=["Eşleştirme"])

class MatchIn(BaseModel):
    match_id: int
class AllocIn(BaseModel):
    invoice_id: int
    amount_kurus: int = Field(gt=0)
class ManualIn(BaseModel):
    transaction_id: int
    allocations: list[AllocIn]

def _match_out(mt: m.ReconciliationMatch):
    return {"match_id": mt.id, "transaction_id": mt.transaction_id, "score": mt.score, "status": mt.status,
            "reasons": json.loads(mt.reasons or "[]"),
            "allocations": [{"invoice_id": a.invoice_id, "invoice_no": db_inv(a).invoice_no,
                             "party": db_inv(a).party_name, "amount_kurus": a.amount_kurus} for a in mt.allocations]}
def db_inv(a): 
    from sqlalchemy.orm import object_session
    return object_session(a).get(m.Invoice, a.invoice_id)

@router.post("/run")
def run(db: Session = Depends(get_db)): return svc.run(db, "manual")

@router.get("/results")
def results(db: Session = Depends(get_db)):
    ms = db.query(m.ReconciliationMatch).filter(m.ReconciliationMatch.status.in_(["SUGGESTED", "APPROVED"])).all()
    return [_match_out(x) for x in ms]

def _alloc(inv, amount):
    return {"invoice_id": inv.id, "invoice_no": inv.invoice_no, "party": inv.party_name, "currency": inv.currency,
            "total_kurus": inv.total_kurus, "remaining_kurus": inv.remaining_kurus, "due_date": inv.due_date.isoformat(),
            "doc_type": inv.doc_type, "amount_kurus": amount}

@router.get("/candidates/{transaction_id}")
def candidates(transaction_id: int, db: Session = Depends(get_db)):
    tx = db.get(m.BankTransaction, transaction_id)
    if not tx: raise BusinessError("Banka hareketi bulunamadı.", 404)
    out = []
    for c in svc.candidates_for(db, tx):
        out.append({"score": c.score, "kind": c.kind, "reasons": c.reasons, "invoice_no_confirmed": c.invoice_no_confirmed,
                    "allocations": [_alloc(db.get(m.Invoice, i), a) for i, a in c.allocations.items()]})
    return {"note": "Skor istatistiksel olasılık değil, kural tabanlı uygunluk puanıdır.", "candidates": out}

@router.post("/approve")
def approve(body: MatchIn, db: Session = Depends(get_db)): svc.approve(db, body.match_id); return {"ok": True}
@router.post("/reject")
def reject(body: MatchIn, db: Session = Depends(get_db)): svc.reject(db, body.match_id); return {"ok": True}
@router.post("/undo")
def undo(body: MatchIn, db: Session = Depends(get_db)): svc.undo(db, body.match_id); return {"ok": True}
@router.post("/manual")
def manual(body: ManualIn, db: Session = Depends(get_db)):
    return {"match_id": svc.manual(db, body.transaction_id, [a.model_dump() for a in body.allocations])}

@router.get("/history")
def history(db: Session = Depends(get_db)):
    """Eşleşme geçmişi: onaylanan, reddedilen ve geri alınan kararlar (silinmez)."""
    ms = db.query(m.ReconciliationMatch).filter(m.ReconciliationMatch.status.in_(["APPROVED", "REJECTED", "UNDONE"])) \
        .order_by(m.ReconciliationMatch.id.desc()).limit(500).all()
    out = []
    for x in ms:
        t = db.get(m.BankTransaction, x.transaction_id); o = _match_out(x)
        out.append({**o, "decided_at": x.decided_at.isoformat() if x.decided_at else None,
                    "tx_date": t.tx_date.isoformat(), "tx_description": t.description, "tx_amount_kurus": t.amount_kurus})
    return out

@router.get("/audit-logs")
def audit_logs(db: Session = Depends(get_db)):
    return [{"at": a.at.isoformat(), "action": a.action, "entity": a.entity, "entity_id": a.entity_id, "detail": a.detail}
            for a in db.query(m.AuditLog).order_by(m.AuditLog.id.desc()).limit(500)]

def _kurus(v: int) -> str: return f"{v // 100}.{v % 100:02d}"

@router.get("/export")
def export(format: str = "xlsx", db: Session = Depends(get_db)):
    import io, pandas as pd
    from fastapi.responses import StreamingResponse
    rows = []
    for t in db.query(m.BankTransaction).order_by(m.BankTransaction.tx_date, m.BankTransaction.id):
        mt = db.query(m.ReconciliationMatch).filter(m.ReconciliationMatch.transaction_id == t.id,
              m.ReconciliationMatch.status.in_(["APPROVED", "SUGGESTED"])).order_by(m.ReconciliationMatch.id.desc()).first()
        invs = ", ".join(db_inv(a).invoice_no for a in mt.allocations) if mt else ""
        rows.append({"Tarih": t.tx_date.isoformat(), "Yön": t.direction, "Açıklama": t.description,
                     "Tutar": _kurus(t.amount_kurus), "Para Birimi": t.currency, "Durum": t.status,
                     "Eşleşen Fatura": invs, "Skor": mt.score if mt else "", "Eşleşme Durumu": mt.status if mt else ""})
    df = pd.DataFrame(rows, columns=["Tarih", "Yön", "Açıklama", "Tutar", "Para Birimi", "Durum", "Eşleşen Fatura", "Skor", "Eşleşme Durumu"])
    buf = io.BytesIO()
    if format == "csv":
        buf.write(df.to_csv(index=False).encode("utf-8-sig")); media, ext = "text/csv", "csv"
    else:
        df.to_excel(buf, index=False, engine="openpyxl"); media, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
    buf.seek(0)
    return StreamingResponse(buf, media_type=media, headers={"Content-Disposition": f"attachment; filename=eslestirme_raporu.{ext}"})
