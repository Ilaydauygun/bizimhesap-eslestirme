import hashlib, itertools
from datetime import date
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database.session import Base
from app import models as m

_seq = itertools.count(1)

@pytest.fixture()
def factory(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    event.listen(eng, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(eng)
    f = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    s = f(); s.add(m.AutomationSettings()); s.add(m.BankAccount(name="TL", iban="TR1", currency="TRY"))
    s.add(m.Customer(name="Çınar Gıda San. Tic. Ltd. Şti.")); s.add(m.Customer(name="Güneş Tekstil A.Ş."))
    s.add(m.Supplier(name="Marmara Kağıt A.Ş.")); s.add(m.Supplier(name="Orhan Ambalaj Ltd. Şti."))
    s.commit(); s.close()
    return f

@pytest.fixture()
def db(factory):
    s = factory(); yield s; s.close()

def mk_inv(db, no, amount, kind="SALE", party=1, cur="TRY", cancelled=False, paid=0, d=date(2026, 10, 1)):
    i = m.Invoice(invoice_no=no, kind=kind, customer_id=party if kind == "SALE" else None,
                  supplier_id=party if kind == "PURCH" else None, issue_date=d, due_date=d,
                  total_kurus=amount, paid_kurus=paid, currency=cur, cancelled=cancelled)
    db.add(i); db.commit(); return i

def mk_tx(db, amount, desc, direction="IN", cur="TRY", cat="PAYMENT", d=date(2026, 10, 5)):
    t = m.BankTransaction(account_id=1, tx_date=d, direction=direction, category=cat, description=desc,
        amount_kurus=amount, currency=cur, status="UNMATCHED" if cat == "PAYMENT" else "OUT_OF_SCOPE",
        dedup_key=hashlib.sha256(f"{next(_seq)}{desc}".encode()).hexdigest()[:32])
    db.add(t); db.commit(); return t

import os
os.environ["DISABLE_SCHEDULER"] = "1"

@pytest.fixture()
def client(factory):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database.session import get_db
    def _db():
        s = factory()
        try: yield s
        finally: s.close()
    app.dependency_overrides[get_db] = _db
    yield TestClient(app)
    app.dependency_overrides.clear()
