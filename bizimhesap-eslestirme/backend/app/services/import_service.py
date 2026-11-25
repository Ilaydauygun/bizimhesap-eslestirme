import hashlib, io, re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import pandas as pd
from sqlalchemy.orm import Session
from app import models as m
from app.services.errors import BusinessError
from app.utils.text import normalize_text
from app.utils.money import parse_tr_amount, to_kurus

CURRENCIES = {"TRY": "TRY", "TL": "TRY", "USD": "USD", "EUR": "EUR"}
DIRECTIONS = {"IN": "IN", "GIRIS": "IN", "OUT": "OUT", "CIKIS": "OUT"}   # borç/alacak varsayılmaz
CATEGORIES = {"PAYMENT": "PAYMENT", "ODEME": "PAYMENT", "TRANSFER": "TRANSFER", "FEE": "FEE", "MASRAF": "FEE",
              "LOAN": "LOAN", "KREDI": "LOAN", "OTHER": "OTHER", "DIGER": "OTHER"}
DOC_TYPES = {"siparis": "Sipariş", "irsaliye": "İrsaliye", "irsaliyelesmis": "İrsaliyeleşmiş",
             "faturalasmis": "Faturalaşmış", "e faturalasmis": "E-Faturalaşmış", "e faturalasmamis": "E-Faturalaşmamış"}
TX_COLS = ["tarih", "yon", "tutar", "para_birimi", "aciklama", "hesap_iban"]
INV_COLS = ["fatura_no", "tur", "cari_unvan", "fatura_tarihi", "vade_tarihi", "tutar", "para_birimi"]

def parse_date(v) -> date:
    s = str(v).strip()
    if not s: raise ValueError("Tarih boş.")
    s = re.split(r"[ T]", s)[0]
    for f in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try: return datetime.strptime(s, f).date()
        except ValueError: pass
    raise ValueError(f"Geçersiz tarih: '{v}'.")

def parse_amount(v) -> int:
    try: k = parse_tr_amount(str(v))
    except (InvalidOperation, ValueError, TypeError): raise ValueError(f"Geçersiz tutar: '{v}'.")
    return k

def read_table(filename: str, content: bytes, required: list[str]) -> pd.DataFrame:
    name = (filename or "").lower()
    try:
        if name.endswith(".csv"):
            try: text = content.decode("utf-8-sig")
            except UnicodeDecodeError: text = content.decode("cp1254")
            df = pd.read_csv(io.StringIO(text), sep=None, engine="python", dtype=str, keep_default_na=False)
        elif name.endswith((".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(content), dtype=str, engine="openpyxl", keep_default_na=False)
        else:
            raise BusinessError("Yalnızca .csv ve .xlsx dosyaları desteklenir.")
    except BusinessError: raise
    except Exception:
        raise BusinessError("Dosya okunamadı veya bozuk. Lütfen şablona uygun bir dosya yükleyin.")
    df.columns = [normalize_text(c).replace(" ", "_") for c in df.columns]
    missing = [c for c in required if c not in df.columns]
    if missing: raise BusinessError("Dosyada zorunlu sütunlar eksik: " + ", ".join(missing))
    if df.empty: raise BusinessError("Dosyada hiç satır yok.")
    return df

def _account(db, key: str) -> m.BankAccount:
    k = re.sub(r"\s", "", key).upper()
    a = db.query(m.BankAccount).filter(m.BankAccount.iban == k).first() or \
        next((x for x in db.query(m.BankAccount) if normalize_text(x.name) == normalize_text(key)), None)
    if not a: raise ValueError(f"Banka hesabı bulunamadı: '{key}'.")
    return a

def dedup_key(account_id, d, direction, amount, desc, ref="") -> str:
    raw = f"{account_id}|{d}|{direction}|{amount}|{normalize_text(desc)}|{normalize_text(ref)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

def make_transaction(db: Session, d: dict, seen: set) -> m.BankTransaction | None:
    """None = mükerrer. ValueError = satır hatası."""
    acc = _account(db, str(d["hesap_iban"]))
    direction = DIRECTIONS.get(normalize_text(str(d["yon"])).upper().replace(" ", ""))
    if not direction: raise ValueError(f"İşlem yönü anlaşılamadı: '{d['yon']}' (IN/OUT veya Giriş/Çıkış olmalı).")
    cat = CATEGORIES.get(normalize_text(str(d.get("kategori") or "PAYMENT")).upper(), None)
    if not cat: raise ValueError(f"Bilinmeyen kategori: '{d.get('kategori')}'.")
    cur = CURRENCIES.get(str(d["para_birimi"]).strip().upper())
    if not cur: raise ValueError(f"Geçersiz para birimi: '{d['para_birimi']}'.")
    if cur != acc.currency: raise ValueError(f"Para birimi ({cur}) hesap para birimiyle ({acc.currency}) uyuşmuyor.")
    amount = parse_amount(d["tutar"])
    if amount <= 0: raise ValueError("Tutar sıfırdan büyük olmalı.")
    dt = parse_date(d["tarih"])
    key = dedup_key(acc.id, dt, direction, amount, d["aciklama"], d.get("referans", ""))
    if key in seen or db.query(m.BankTransaction.id).filter_by(dedup_key=key).first(): return None
    seen.add(key)
    t = m.BankTransaction(account_id=acc.id, tx_date=dt, direction=direction, category=cat, description=str(d["aciklama"]),
                          amount_kurus=amount, currency=cur, dedup_key=key,
                          status="UNMATCHED" if cat == "PAYMENT" else "OUT_OF_SCOPE")
    db.add(t); db.flush(); return t

def _party(db, kind, name):
    model = m.Customer if kind == "SALE" else m.Supplier
    n = normalize_text(name)
    if not n: raise ValueError("Cari ünvan boş.")
    for p in db.query(model):
        if normalize_text(p.name) == n: return p
    p = model(name=name.strip()); db.add(p); db.flush(); return p

def make_invoice(db: Session, d: dict, seen: set) -> m.Invoice | None:
    kind = {"SATIS": "SALE", "SALE": "SALE", "ALIS": "PURCH", "PURCH": "PURCH"}.get(normalize_text(str(d["tur"])).upper())
    if not kind: raise ValueError(f"Fatura türü anlaşılamadı: '{d['tur']}' (Satış/Alış).")
    no = str(d["fatura_no"]).strip()
    if not no: raise ValueError("Fatura numarası boş.")
    if (no, kind) in seen or db.query(m.Invoice.id).filter_by(invoice_no=no, kind=kind).first(): return None
    cur = CURRENCIES.get(str(d["para_birimi"]).strip().upper())
    if not cur: raise ValueError(f"Geçersiz para birimi: '{d['para_birimi']}'.")
    total = parse_amount(d["tutar"]); paid = parse_amount(d["odenen"]) if str(d.get("odenen", "")).strip() else 0
    if total <= 0: raise ValueError("Fatura tutarı sıfırdan büyük olmalı.")
    if paid < 0 or paid > total: raise ValueError("Ödenen tutar 0 ile fatura tutarı arasında olmalı.")
    issue, due = parse_date(d["fatura_tarihi"]), parse_date(d["vade_tarihi"])
    if due < issue: raise ValueError("Vade tarihi fatura tarihinden önce olamaz.")
    doc = DOC_TYPES.get(normalize_text(str(d.get("belge_tipi") or "faturalasmis")))
    if not doc: raise ValueError(f"Bilinmeyen belge tipi: '{d.get('belge_tipi')}'.")
    cancelled = normalize_text(str(d.get("iptal", ""))) in {"evet", "1", "true", "iptal"}
    party = _party(db, kind, str(d["cari_unvan"]))
    inv = m.Invoice(invoice_no=no, kind=kind, doc_type=doc, customer_id=party.id if kind == "SALE" else None,
                    supplier_id=party.id if kind == "PURCH" else None, issue_date=issue, due_date=due,
                    total_kurus=total, paid_kurus=paid, currency=cur, cancelled=cancelled)
    db.add(inv); db.flush(); seen.add((no, kind)); return inv

def import_rows(db: Session, df: pd.DataFrame, maker) -> dict:
    ok, dup, errors, created, seen = 0, 0, [], [], set()
    try:
        for idx, row in df.iterrows():
            try:
                with db.begin_nested():
                    obj = maker(db, row.to_dict(), seen)
                if obj is None: dup += 1
                else: ok += 1; created.append(obj)
            except ValueError as e:
                errors.append({"row": int(idx) + 2, "message": str(e)})
        db.commit()
    except Exception:
        db.rollback(); raise
    return {"imported": ok, "duplicates": dup, "errors": errors, "ids": [o.id for o in created]}
