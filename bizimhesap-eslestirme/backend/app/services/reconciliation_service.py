import json, threading
from datetime import datetime
from sqlalchemy import update, func
from sqlalchemy.orm import Session
from app import models as m
from app.services import matching_engine as eng
from app.services.errors import BusinessError

_RUN_LOCK = threading.Lock()

def load_settings(db: Session) -> eng.Settings:
    row = db.query(m.AutomationSettings).first() or m.AutomationSettings()
    return eng.Settings(row.w_amount or 40, row.w_name or 25, row.w_invoice_no or 25, row.w_date or 10,
                        row.date_tolerance_days if row.date_tolerance_days is not None else 30, row.min_score or 60)

def audit(db, action, entity, entity_id, detail=""):
    db.add(m.AuditLog(action=action, entity=entity, entity_id=entity_id, detail=detail))

def _allocated(db, tx_id) -> int:
    return db.query(func.coalesce(func.sum(m.ReconciliationAllocation.amount_kurus), 0)) \
        .join(m.ReconciliationMatch).filter(m.ReconciliationMatch.transaction_id == tx_id,
                                            m.ReconciliationMatch.status == "APPROVED").scalar()

def refresh_tx_status(db, tx: m.BankTransaction):
    if tx.category != "PAYMENT": tx.status = "OUT_OF_SCOPE"; return
    alloc = _allocated(db, tx.id)
    if alloc == 0:
        has_sug = db.query(m.ReconciliationMatch).filter_by(transaction_id=tx.id, status="SUGGESTED").count() > 0
        tx.status = "PENDING" if has_sug else "UNMATCHED"
    elif alloc == tx.amount_kurus: tx.status = "MATCHED"
    else: tx.status = "PARTIAL"

def _to_tx(db, t: m.BankTransaction) -> eng.Tx:
    return eng.Tx(t.id, t.direction, t.category, t.description, t.amount_kurus - _allocated(db, t.id),
                  t.currency, t.tx_date)

def _to_inv(i: m.Invoice) -> eng.Inv:
    return eng.Inv(i.id, i.invoice_no, i.kind, i.party_name, i.remaining_kurus, i.currency,
                   i.issue_date, i.due_date, i.cancelled, i.doc_type)

def candidates_for(db: Session, tx: m.BankTransaction):
    s = load_settings(db)
    invs = [_to_inv(i) for i in db.query(m.Invoice).filter(m.Invoice.cancelled == False)]  # noqa: E712
    return eng.find_candidates(_to_tx(db, tx), invs, s)

def _rejected_signatures(db, tx_id):
    rows = db.query(m.ReconciliationMatch).filter_by(transaction_id=tx_id, status="REJECTED").all()
    return {frozenset(a.invoice_id for a in r.allocations) for r in rows}

def run(db: Session, trigger: str = "manual", tx_ids: list[int] | None = None) -> dict:
    if not _RUN_LOCK.acquire(blocking=False):
        if trigger == "event": return {"processed": 0, "failed": 0, "skipped": True}  # zamanlayıcı yakalar
        raise BusinessError("Eşleştirme zaten çalışıyor. Lütfen bitmesini bekleyin.", 409)
    log = m.AutomationLog(trigger=trigger)
    try:
        settings = load_settings(db)
        auto_enabled = (db.query(m.AutomationSettings).first() or m.AutomationSettings(auto_approve=False)).auto_approve
        invs = [_to_inv(i) for i in db.query(m.Invoice).filter(m.Invoice.cancelled == False)]  # noqa: E712
        ok = fail = 0
        q = db.query(m.BankTransaction).filter(m.BankTransaction.status.in_(["UNMATCHED", "PENDING", "PARTIAL"]))
        if tx_ids is not None: q = q.filter(m.BankTransaction.id.in_(tx_ids))
        txs = q.all()
        for t in txs:
            try:
                if t.category != "PAYMENT": t.status = "OUT_OF_SCOPE"; continue
                rej = _rejected_signatures(db, t.id)
                cands = [c for c in eng.find_candidates(_to_tx(db, t), invs, settings) if c.invoice_ids not in rej]
                d = eng.decide(cands)
                old_sug = db.query(m.ReconciliationMatch).filter_by(transaction_id=t.id, status="SUGGESTED").all()
                keep = None
                if cands:
                    for o in old_sug:  # aynı öneri tekrar çıktıysa yeni kayıt açma (idempotent)
                        if o.score == cands[0].score and {a.invoice_id: a.amount_kurus for a in o.allocations} == cands[0].allocations:
                            keep = o
                for o in old_sug:      # geçmiş silinmez, yalnızca "yerine yenisi geldi" işaretlenir
                    if o is not keep: o.status = "SUPERSEDED"
                db.flush()
                if keep:
                    refresh_tx_status(db, t)
                    if auto_enabled and d["auto_ok"]: _approve(db, keep.id, actor="auto")
                elif cands:
                    top = cands[0]
                    reasons = list(top.reasons)
                    if d["ambiguous"]: reasons.insert(0, "UYARI: Birden fazla güçlü aday var; otomatik kayıt yapılmadı.")
                    reasons.append("Skor olasılık değil, kural tabanlı uygunluk puanıdır.")
                    mt = m.ReconciliationMatch(transaction_id=t.id, score=top.score, reasons=json.dumps(reasons, ensure_ascii=False))
                    db.add(mt); db.flush()
                    for inv_id, amt in top.allocations.items():
                        db.add(m.ReconciliationAllocation(match_id=mt.id, invoice_id=inv_id, amount_kurus=amt))
                    db.flush()
                    audit(db, "SUGGEST", "match", mt.id, f"tx={t.id} skor={top.score}")
                    refresh_tx_status(db, t)
                    if auto_enabled and d["auto_ok"]:
                        _approve(db, mt.id, actor="auto"); invs = [_to_inv(i) for i in db.query(m.Invoice).filter(m.Invoice.cancelled == False)]  # noqa: E712
                else:
                    refresh_tx_status(db, t)
                ok += 1
            except BusinessError as e:
                fail += 1; log.message += f"tx {t.id}: {e.message}\n"
        log.success_count, log.fail_count = ok, fail
        db.add(log); audit(db, "RUN", "automation", None, f"{trigger}: ok={ok} fail={fail}")
        db.commit()
        return {"processed": ok, "failed": fail}
    except Exception:
        db.rollback(); raise
    finally:
        _RUN_LOCK.release()

def _approve(db: Session, match_id: int, actor: str):
    # 1) Atomik durum geçişi: aynı eşleşmenin eş zamanlı onayını engeller.
    res = db.execute(update(m.ReconciliationMatch).where(m.ReconciliationMatch.id == match_id,
                     m.ReconciliationMatch.status == "SUGGESTED")
                     .values(status="APPROVED", decided_at=datetime.utcnow()))
    if res.rowcount != 1:
        raise BusinessError("Bu eşleşme zaten işlenmiş veya bulunamadı.", 409)
    mt = db.get(m.ReconciliationMatch, match_id)
    tx = db.get(m.BankTransaction, mt.transaction_id)
    for a in mt.allocations:
        r = db.execute(update(m.Invoice).where(m.Invoice.id == a.invoice_id, m.Invoice.cancelled == False,  # noqa: E712
                       m.Invoice.paid_kurus + a.amount_kurus <= m.Invoice.total_kurus)
                       .values(paid_kurus=m.Invoice.paid_kurus + a.amount_kurus))
        if r.rowcount != 1:
            raise BusinessError("Fatura kalan borcu aşılıyor veya fatura iptal edilmiş.", 409)
    if _allocated(db, tx.id) > tx.amount_kurus:
        raise BusinessError("Banka hareketine ayrılan toplam tutar işlem tutarını aşıyor.", 409)
    db.flush(); refresh_tx_status(db, tx)
    audit(db, "APPROVE", "match", match_id, f"actor={actor}")

def approve(db: Session, match_id: int, actor="user"):
    try:
        _approve(db, match_id, actor); db.commit()
    except Exception:
        db.rollback(); raise

def reject(db: Session, match_id: int):
    try:
        res = db.execute(update(m.ReconciliationMatch).where(m.ReconciliationMatch.id == match_id,
                         m.ReconciliationMatch.status == "SUGGESTED").values(status="REJECTED", decided_at=datetime.utcnow()))
        if res.rowcount != 1: raise BusinessError("Bu eşleşme zaten işlenmiş veya bulunamadı.", 409)
        mt = db.get(m.ReconciliationMatch, match_id)
        refresh_tx_status(db, db.get(m.BankTransaction, mt.transaction_id))
        audit(db, "REJECT", "match", match_id); db.commit()
    except Exception:
        db.rollback(); raise

def undo(db: Session, match_id: int):
    try:
        res = db.execute(update(m.ReconciliationMatch).where(m.ReconciliationMatch.id == match_id,
                         m.ReconciliationMatch.status == "APPROVED").values(status="UNDONE", decided_at=datetime.utcnow()))
        if res.rowcount != 1: raise BusinessError("Yalnızca onaylanmış eşleşme geri alınabilir.", 409)
        mt = db.get(m.ReconciliationMatch, match_id)
        for a in mt.allocations:
            r = db.execute(update(m.Invoice).where(m.Invoice.id == a.invoice_id, m.Invoice.paid_kurus >= a.amount_kurus)
                           .values(paid_kurus=m.Invoice.paid_kurus - a.amount_kurus))
            if r.rowcount != 1: raise BusinessError("Fatura ödeme tutarı geri alınamadı.", 409)
        db.flush(); refresh_tx_status(db, db.get(m.BankTransaction, mt.transaction_id))
        audit(db, "UNDO", "match", match_id); db.commit()
    except Exception:
        db.rollback(); raise

def manual(db: Session, tx_id: int, allocations: list[dict]):
    try:
        tx = db.get(m.BankTransaction, tx_id)
        if not tx: raise BusinessError("Banka hareketi bulunamadı.", 404)
        if tx.category != "PAYMENT": raise BusinessError("Bu hareket fatura eşleştirmesi kapsamı dışında.")
        if not allocations: raise BusinessError("En az bir fatura seçilmelidir.")
        ids = [a["invoice_id"] for a in allocations]
        if len(set(ids)) != len(ids): raise BusinessError("Aynı fatura birden fazla kez seçilemez.")
        avail = eng.Tx(tx.id, tx.direction, tx.category, tx.description, tx.amount_kurus - _allocated(db, tx.id), tx.currency, tx.tx_date)
        total = 0
        for a in allocations:
            inv = db.get(m.Invoice, a["invoice_id"])
            if not inv: raise BusinessError("Fatura bulunamadı.", 404)
            if not eng.is_eligible(avail, _to_inv(inv)):
                raise BusinessError(f"{inv.invoice_no} bu hareketle eşleştirilemez (yön, para birimi, iptal veya ödenmiş).")
            if a["amount_kurus"] <= 0 or a["amount_kurus"] > inv.remaining_kurus:
                raise BusinessError(f"{inv.invoice_no} için tutar kalan borcu aşıyor.")
            total += a["amount_kurus"]
        if total > avail.available_kurus: raise BusinessError("Toplam tutar banka hareketinin kalan tutarını aşıyor.")
        for o in db.query(m.ReconciliationMatch).filter_by(transaction_id=tx.id, status="SUGGESTED"):
            o.status = "SUPERSEDED"      # kullanıcı kararı sistem önerisinin yerini alır (kayıt silinmez)
        mt = m.ReconciliationMatch(transaction_id=tx.id, score=0, reasons=json.dumps(["Kullanıcı tarafından manuel eşleştirildi."], ensure_ascii=False))
        db.add(mt); db.flush()
        for a in allocations:
            db.add(m.ReconciliationAllocation(match_id=mt.id, invoice_id=a["invoice_id"], amount_kurus=a["amount_kurus"]))
        db.flush()
        # SUGGESTED -> APPROVED aynı transaction içinde
        _approve(db, mt.id, actor="user-manual"); db.commit()
        return mt.id
    except Exception:
        db.rollback(); raise
