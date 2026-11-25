import io
import openpyxl
import pytest
from app import models as m
from app.services import reconciliation_service as svc
from app.tests.conftest import mk_inv

INV_CSV = ("fatura_no;tur;cari_unvan;fatura_tarihi;vade_tarihi;tutar;odenen;para_birimi\n"
           "SF-2026-101;Satış;Çınar Gıda San. Tic. Ltd. Şti.;01.10.2026;31.10.2026;5.000,00;;TRY\n"
           "SF-2026-102;Satış;Güneş Tekstil A.Ş.;02.10.2026;01.11.2026;1.250,50;250,50;TRY\n")
TX_CSV = ("tarih;yon;tutar;para_birimi;aciklama;hesap_iban\n"
          "05.10.2026;Giriş;5.000,00;TRY;SF-2026-101 nolu fatura ÇINAR GIDA;TR1\n")

def up(name, text): return {"file": (name, text.encode("utf-8"), "text/csv")}

def test_invoice_import_turkish_amounts(client, db):
    r = client.post("/api/invoices/import", files=up("f.csv", INV_CSV)).json()
    assert r["imported"] == 2 and r["errors"] == []
    inv = db.query(m.Invoice).filter_by(invoice_no="SF-2026-102").one()
    assert (inv.total_kurus, inv.paid_kurus, inv.payment_status) == (125050, 25050, "Kısmen Ödendi")

def test_reimport_is_duplicate_safe(client):
    client.post("/api/invoices/import", files=up("f.csv", INV_CSV))
    r = client.post("/api/invoices/import", files=up("f.csv", INV_CSV)).json()
    assert r["imported"] == 0 and r["duplicates"] == 2

def test_tx_import_triggers_event_matching(client, db):
    client.post("/api/invoices/import", files=up("f.csv", INV_CSV))
    r = client.post("/api/bank-transactions/import", files=up("t.csv", TX_CSV)).json()
    assert r["imported"] == 1
    assert db.query(m.ReconciliationMatch).filter_by(status="SUGGESTED").count() == 1   # olay tabanlı eşleştirme çalıştı
    assert db.query(m.AutomationLog).filter_by(trigger="event").count() == 1

def test_duplicate_transaction_rows_in_file(client):
    client.post("/api/invoices/import", files=up("f.csv", INV_CSV))
    r = client.post("/api/bank-transactions/import", files=up("t.csv", TX_CSV + TX_CSV.split("\n")[1] + "\n")).json()
    assert r["imported"] == 1 and r["duplicates"] == 1

def test_bad_rows_reported_good_rows_saved(client):
    bad = TX_CSV + ("xx.10.2026;Giriş;100,00;TRY;a;TR1\n05.10.2026;Borç;100,00;TRY;b;TR1\n"
                    "05.10.2026;IN;abc;TRY;c;TR1\n05.10.2026;IN;100,00;USD;d;TR1\n06.10.2026;IN;100,00;TRY;e;TR999\n")
    r = client.post("/api/bank-transactions/import", files=up("t.csv", bad)).json()
    assert r["imported"] == 1 and len(r["errors"]) == 5
    assert any("Borç" in e["message"] for e in r["errors"])      # borç/alacak anlamı varsayılmaz

def test_missing_columns_and_wrong_format(client):
    r = client.post("/api/invoices/import", files=up("f.csv", "a;b\n1;2\n"))
    assert r.status_code == 422 and "eksik" in r.json()["detail"]
    r = client.post("/api/invoices/import", files={"file": ("f.txt", b"x", "text/plain")})
    assert r.status_code == 422
    r = client.post("/api/invoices/import", files={"file": ("f.xlsx", b"bozuk-dosya", "application/octet-stream")})
    assert r.status_code == 422 and "bozuk" in r.json()["detail"]

def test_excel_import(client):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["fatura_no", "tur", "cari_unvan", "fatura_tarihi", "vade_tarihi", "tutar", "para_birimi"])
    ws.append(["AF-2026-101", "Alış", "Marmara Kağıt A.Ş.", "01.10.2026", "30.10.2026", "2000,00", "TRY"])
    buf = io.BytesIO(); wb.save(buf)
    r = client.post("/api/invoices/import", files={"file": ("f.xlsx", buf.getvalue(), "application/octet-stream")}).json()
    assert r["imported"] == 1

def test_manual_tx_and_duplicate(client):
    body = {"account_id": 1, "date": "2026-10-05", "direction": "IN", "amount": "100.50", "description": "test"}
    assert client.post("/api/bank-transactions", json=body).status_code == 201
    r = client.post("/api/bank-transactions", json=body)
    assert r.status_code == 409 and "mükerrer" in r.json()["detail"]
    assert client.post("/api/bank-transactions", json={**body, "direction": "X"}).status_code == 422

def test_settings_roundtrip_and_validation(client):
    s = client.get("/api/automation/settings").json()
    assert s["interval_minutes"] == 15 and s["w_amount"] == 40
    ok = {k: s[k] for k in ["enabled", "interval_minutes", "min_score", "auto_approve", "date_tolerance_days",
                            "w_amount", "w_name", "w_invoice_no", "w_date"]}
    ok.update(min_score=70, date_tolerance_days=10)
    assert client.put("/api/automation/settings", json=ok).json()["min_score"] == 70
    assert client.put("/api/automation/settings", json={**ok, "interval_minutes": 0}).status_code == 422
    z = {**ok, "w_amount": 0, "w_name": 0, "w_invoice_no": 0, "w_date": 0}
    assert client.put("/api/automation/settings", json=z).status_code == 422

def test_run_blocked_while_another_run_in_progress(client):
    assert svc._RUN_LOCK.acquire(blocking=False)
    try:
        r = client.post("/api/reconciliation/run")
        assert r.status_code == 409 and "zaten çalışıyor" in r.json()["detail"]
        assert svc.run(client.app.dependency_overrides and next(iter(client.app.dependency_overrides.values()))().__next__(), "event", [1]) == \
            {"processed": 0, "failed": 0, "skipped": True}   # olay tetikleyici kilitliyken sessizce atlanır
    finally:
        svc._RUN_LOCK.release()

def test_auto_approve_only_when_enabled_and_safe(client, db):
    mk_inv(db, "SF-2026-101", 500000)
    base = {"account_id": 1, "date": "2026-10-05", "direction": "IN", "amount": "5000.00",
            "description": "SF-2026-101 Çınar Gıda"}
    client.post("/api/bank-transactions", json=base)
    assert db.query(m.ReconciliationMatch).filter_by(status="APPROVED").count() == 0      # varsayılan: onay şart
    s = client.get("/api/automation/settings").json()
    s = {k: s[k] for k in ["enabled", "interval_minutes", "min_score", "auto_approve", "date_tolerance_days", "w_amount", "w_name", "w_invoice_no", "w_date"]}
    client.put("/api/automation/settings", json={**s, "auto_approve": True})
    mk_inv(db, "SF-2026-102", 700000)
    client.post("/api/bank-transactions", json={**base, "amount": "7000.00", "description": "SF-2026-102 Çınar Gıda"})
    db.expire_all()
    assert db.query(m.ReconciliationMatch).filter_by(status="APPROVED").count() == 1
    assert db.query(m.Invoice).filter_by(invoice_no="SF-2026-102").one().payment_status == "Ödendi"

def test_history_and_export(client, db):
    mk_inv(db, "SF-2026-101", 500000)
    client.post("/api/bank-transactions", json={"account_id": 1, "date": "2026-10-05", "direction": "IN",
                "amount": "5000.00", "description": "SF-2026-101 Çınar Gıda"})
    mid = db.query(m.ReconciliationMatch).one().id
    client.post("/api/reconciliation/approve", json={"match_id": mid}); client.post("/api/reconciliation/undo", json={"match_id": mid})
    h = client.get("/api/reconciliation/history").json()
    assert h[0]["status"] == "UNDONE"
    x = client.get("/api/reconciliation/export?format=xlsx"); assert x.status_code == 200 and x.content[:2] == b"PK"
    c = client.get("/api/reconciliation/export?format=csv"); assert "SF-2026-101" in c.content.decode("utf-8-sig")

def test_manual_choice_supersedes_system_suggestion(client, db):
    a = mk_inv(db, "SF-2026-101", 500000); b = mk_inv(db, "SF-2026-102", 500000)
    client.post("/api/bank-transactions", json={"account_id": 1, "date": "2026-10-05", "direction": "IN",
                "amount": "5000.00", "description": "Çınar Gıda havale"})
    cands = client.get("/api/reconciliation/candidates/1").json()["candidates"]
    assert len(cands) == 2 and cands[0]["allocations"][0]["party"] and "remaining_kurus" in cands[0]["allocations"][0]
    chosen = cands[1]["allocations"][0]
    r = client.post("/api/reconciliation/manual", json={"transaction_id": 1, "allocations": [
        {"invoice_id": chosen["invoice_id"], "amount_kurus": 500000}]})
    assert r.status_code == 200
    db.expire_all()
    assert db.query(m.ReconciliationMatch).filter_by(status="SUGGESTED").count() == 0
    assert db.get(m.BankTransaction, 1).status == "MATCHED"
