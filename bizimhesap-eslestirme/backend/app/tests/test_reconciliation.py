import threading
import pytest
from sqlalchemy.exc import IntegrityError
from app import models as m
from app.services import reconciliation_service as svc, matching_engine as eng
from app.services.errors import BusinessError
from app.utils.text import normalize_text, extract_invoice_numbers, company_tokens
from app.utils.money import parse_tr_amount
from app.tests.conftest import mk_inv, mk_tx

def cands(db, tx): return svc.candidates_for(db, db.get(m.BankTransaction, tx.id))

def test_full_payment_is_strong_and_auto_eligible(db):
    mk_inv(db, "SF-2026-001", 500000)
    t = mk_tx(db, 500000, "SF-2026-001 nolu fatura ÇINAR GIDA")
    c = cands(db, t); d = eng.decide(c)
    assert c[0].kind == "FULL" and c[0].score >= 90 and d["auto_ok"]

def test_partial_payment_updates_invoice(db):
    inv = mk_inv(db, "SF-2026-001", 500000)
    t = mk_tx(db, 300000, "SF-2026-001 kismi odeme Çınar Gıda")
    c = cands(db, t); assert c[0].kind == "PARTIAL" and not eng.decide(c)["auto_ok"]
    svc.run(db); mt = db.query(m.ReconciliationMatch).one(); svc.approve(db, mt.id)
    db.refresh(inv); assert (inv.paid_kurus, inv.remaining_kurus, inv.payment_status) == (300000, 200000, "Kısmen Ödendi")

def test_bulk_payment(db):
    mk_inv(db, "FTR-001", 400000); mk_inv(db, "FTR-002", 600000)
    t = mk_tx(db, 1000000, "Çınar Gıda toplu odeme FTR-001 FTR-002")
    c = cands(db, t); b = [x for x in c if x.kind == "BULK"]
    assert b and len(b[0].allocations) == 2 and not eng.decide(c)["auto_ok"]

def test_overpayment_needs_review_and_never_spills(db):
    inv = mk_inv(db, "SF-2026-001", 500000)
    t = mk_tx(db, 600000, "SF-2026-001 Çınar Gıda")
    c = cands(db, t); assert c[0].kind == "OVERPAY" and not eng.decide(c)["auto_ok"]
    svc.run(db); svc.approve(db, db.query(m.ReconciliationMatch).one().id)
    db.refresh(inv); db.refresh(t)
    assert inv.paid_kurus == 500000 and t.status == "PARTIAL"   # fazla 1.000 TL başka faturaya aktarılmadı

def test_wrong_customer_no_candidate(db):
    mk_inv(db, "SF-2026-001", 500000, party=1)
    assert cands(db, mk_tx(db, 500000, "Güneş Tekstil havale")) == [] or \
        all(x.score < 90 for x in cands(db, mk_tx(db, 500000, "Güneş Tekstil havale")))

def test_wrong_supplier(db):
    mk_inv(db, "AF-2026-001", 200000, kind="PURCH", party=1)
    t = mk_tx(db, 200000, "Orhan Ambalaj odeme", direction="OUT")
    assert not [x for x in cands(db, t) if x.score >= 90]

def test_currency_mismatch(db):
    mk_inv(db, "SF-2026-001", 500000, cur="USD")
    assert cands(db, mk_tx(db, 500000, "SF-2026-001 Çınar Gıda", cur="TRY")) == []

def test_same_amount_invoices_are_ambiguous(db):
    mk_inv(db, "SF-2026-001", 500000); mk_inv(db, "SF-2026-002", 500000)
    c = cands(db, mk_tx(db, 500000, "Çınar Gıda havale")); d = eng.decide(c)
    assert len(c) == 2 and d["ambiguous"] and not d["auto_ok"]

def test_duplicate_bank_transaction_rejected(db):
    t = mk_tx(db, 1000, "x")
    db.add(m.BankTransaction(account_id=1, tx_date=t.tx_date, direction="IN", category="PAYMENT", description="x",
                             amount_kurus=1000, currency="TRY", dedup_key=t.dedup_key))
    with pytest.raises(IntegrityError): db.commit()

def test_cancelled_and_fully_paid_invoices_excluded(db):
    mk_inv(db, "SF-2026-001", 500000, cancelled=True); mk_inv(db, "SF-2026-002", 500000, paid=500000)
    assert cands(db, mk_tx(db, 500000, "SF-2026-001 SF-2026-002 Çınar Gıda")) == []

def test_undo_restores_invoice(db):
    inv = mk_inv(db, "SF-2026-001", 500000); t = mk_tx(db, 500000, "SF-2026-001 Çınar Gıda")
    svc.run(db); mid = db.query(m.ReconciliationMatch).one().id; svc.approve(db, mid)
    db.refresh(inv); assert inv.payment_status == "Ödendi"
    svc.undo(db, mid); db.refresh(inv); db.refresh(t)
    assert inv.paid_kurus == 0 and inv.payment_status == "Ödenmedi" and t.status == "PENDING" or t.status == "UNMATCHED"
    assert db.query(m.AuditLog).filter_by(action="UNDO").count() == 1   # geçmiş silinmez

def test_rerun_is_idempotent_and_no_double_payment(db):
    inv = mk_inv(db, "SF-2026-001", 500000); mk_tx(db, 500000, "SF-2026-001 Çınar Gıda")
    svc.run(db); svc.run(db)
    assert db.query(m.ReconciliationMatch).count() == 1      # aynı öneri tekrar kaydedilmedi
    svc.approve(db, db.query(m.ReconciliationMatch).one().id); svc.run(db)
    db.refresh(inv); assert inv.paid_kurus == 500000
    assert db.query(m.ReconciliationAllocation).count() == 1

def test_double_approve_rejected(db):
    mk_inv(db, "SF-2026-001", 500000); mk_tx(db, 500000, "SF-2026-001 Çınar Gıda"); svc.run(db)
    mid = db.query(m.ReconciliationMatch).one().id; svc.approve(db, mid)
    with pytest.raises(BusinessError): svc.approve(db, mid)

def test_concurrent_approval_only_one_wins(factory):
    s = factory(); inv = mk_inv(s, "SF-2026-001", 500000); mk_tx(s, 500000, "SF-2026-001 Çınar Gıda"); svc.run(s)
    mid = s.query(m.ReconciliationMatch).one().id; s.close()
    res, bar = [], threading.Barrier(2)
    def work():
        d = factory(); bar.wait()
        try: svc.approve(d, mid); res.append("ok")
        except BusinessError: res.append("err")
        finally: d.close()
    th = [threading.Thread(target=work) for _ in range(2)]; [t.start() for t in th]; [t.join() for t in th]
    assert sorted(res) == ["err", "ok"]
    s = factory(); assert s.get(m.Invoice, inv.id).paid_kurus == 500000

def test_manual_cannot_exceed_remaining(db):
    inv = mk_inv(db, "SF-2026-001", 500000); t = mk_tx(db, 900000, "serbest")
    with pytest.raises(BusinessError): svc.manual(db, t.id, [{"invoice_id": inv.id, "amount_kurus": 600000}])
    db.refresh(inv); assert inv.paid_kurus == 0   # rollback

def test_out_of_scope_transactions_skipped(db):
    mk_inv(db, "SF-2026-001", 500000)
    t = mk_tx(db, 500000, "Hesaplar arasi transfer SF-2026-001", cat="TRANSFER", direction="OUT")
    svc.run(db); db.refresh(t); assert t.status == "OUT_OF_SCOPE" and db.query(m.ReconciliationMatch).count() == 0

def test_turkish_normalization_and_parsing():
    assert normalize_text("ÇINAR GIDA ŞTİ.") == "cinar gida sti"
    assert company_tokens("Güneş Tekstil A.Ş.") == ["gunes", "tekstil"]
    assert "SF2026001" in extract_invoice_numbers("sf-2026-001 nolu fatura")
    assert parse_tr_amount("1.234,56") == 123456
    with pytest.raises(TypeError):
        from app.utils.money import to_kurus; to_kurus(1.5)
