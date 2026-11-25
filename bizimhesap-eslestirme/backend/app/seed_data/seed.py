"""Sentetik veri üretici: python -m app.seed_data.seed"""
import hashlib, random
from datetime import date, timedelta
from app.database.session import Base, engine, SessionLocal
from app import models as m

def dedup(acc, d, direction, amt, desc):
    return hashlib.sha256(f"{acc}|{d}|{direction}|{amt}|{desc}".encode()).hexdigest()[:32]

CUST = ["Anadolu Yapı Ltd. Şti.", "Güneş Tekstil A.Ş.", "Çınar Gıda San. Tic. Ltd. Şti.", "Ege Lojistik A.Ş.",
        "Yıldız Elektronik Ltd.", "Işık Mobilya A.Ş.", "Özkan İnşaat Ltd. Şti.", "Doğu Otomotiv A.Ş.",
        "Başak Eczacılık Ltd.", "Şahin Danışmanlık Ltd. Şti.", "Mavi Deniz Turizm A.Ş.", "Kuzey Plastik Ltd.",
        "Ümit Market Ltd. Şti.", "Gökçe Matbaa A.Ş.", "Tekin Makine San. A.Ş."]
SUPP = ["Marmara Kağıt A.Ş.", "Orhan Ambalaj Ltd. Şti.", "Çelik Metal San. A.Ş.", "Bilgi Yazılım Ltd.",
        "Ankara Enerji A.Ş.", "Güven Temizlik Ltd. Şti.", "Pınar Kırtasiye Ltd.", "Şen Nakliyat A.Ş.",
        "Global Hosting Inc.", "Euro Parts GmbH"]

def run():
    Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
    rnd = random.Random(42)
    db = SessionLocal()
    accs = [m.BankAccount(name="Ana Hesap TL", iban="TR000000000000000000000001", currency="TRY"),
            m.BankAccount(name="Döviz Hesabı USD", iban="TR000000000000000000000002", currency="USD"),
            m.BankAccount(name="Döviz Hesabı EUR", iban="TR000000000000000000000003", currency="EUR")]
    custs = [m.Customer(name=n, tax_no=f"10000000{i:02d}") for i, n in enumerate(CUST)]
    supps = [m.Supplier(name=n, tax_no=f"20000000{i:02d}") for i, n in enumerate(SUPP)]
    db.add_all(accs + custs + supps); db.flush()
    base = date(2026, 10, 1)
    invs = []
    for i in range(30):
        cur = "TRY" if i < 26 else ("USD" if i < 28 else "EUR")
        amt = rnd.choice([1000, 1500, 2500, 3000, 4000, 5000, 6000, 7500, 10000]) * 100
        invs.append(m.Invoice(invoice_no=f"SF-2026-{i+1:03d}", kind="SALE", customer_id=custs[i % 15].id,
            issue_date=base + timedelta(days=i), due_date=base + timedelta(days=i + 30),
            total_kurus=amt, currency=cur, cancelled=(i == 29)))
    for i in range(20):
        amt = rnd.choice([800, 1200, 2000, 3500, 4500, 9000]) * 100
        invs.append(m.Invoice(invoice_no=f"AF-2026-{i+1:03d}", kind="PURCH", supplier_id=supps[i % 10].id,
            issue_date=base + timedelta(days=i), due_date=base + timedelta(days=i + 30),
            total_kurus=amt, currency="TRY" if i < 18 else "USD"))
    # senaryo: aynı tutarlı faturalar (aynı müşteri farklı no) + toplu ödeme
    invs[0].total_kurus = invs[1].total_kurus = 500000
    invs[0].customer_id = invs[1].customer_id = custs[0].id
    invs[2].total_kurus, invs[3].total_kurus = 400000, 600000
    invs[2].customer_id = invs[3].customer_id = custs[1].id
    invs[0].currency = invs[1].currency = invs[2].currency = invs[3].currency = "TRY"
    db.add_all(invs); db.flush()

    txs = []
    def tx(acc, d, direction, amt, desc, cat="PAYMENT"):
        txs.append(m.BankTransaction(account_id=acc.id, tx_date=base + timedelta(days=d), direction=direction,
            category=cat, description=desc, amount_kurus=amt, currency=acc.currency,
            status=("UNMATCHED" if cat == "PAYMENT" else "OUT_OF_SCOPE"),
            dedup_key=dedup(acc.id, d, direction, amt, desc)))
    tl, usd, eur = accs
    # tam ödeme (fatura no açık)
    for i in range(4, 14):
        inv = invs[i]
        tx(accs[0] if inv.currency == "TRY" else usd, i + 5, "IN", inv.total_kurus,
           f"{inv.invoice_no} nolu fatura odemesi {CUST[i % 15].upper()}")
    # kısmi ödeme
    tx(tl, 20, "IN", 300000, f"{invs[14].invoice_no} kismi odeme {CUST[14 % 15]}")
    # toplu ödeme
    tx(tl, 21, "IN", 1000000, f"{CUST[1]} {invs[2].invoice_no} {invs[3].invoice_no} toplu odeme")
    # fazla ödeme
    tx(tl, 22, "IN", 600000, f"{invs[15].invoice_no} {CUST[15 % 15]}")
    # aynı tutarlı adaylar (fatura no yok)
    tx(tl, 23, "IN", 500000, f"{CUST[0]} havale")
    # yanlış para birimi
    tx(tl, 24, "IN", invs[26].total_kurus, f"{invs[26].invoice_no} odeme")
    # alış ödemeleri
    for i in range(30, 40):
        inv = invs[i]
        tx(tl if inv.currency == "TRY" else usd, i - 5, "OUT", inv.total_kurus,
           f"{inv.invoice_no} {SUPP[(i - 30) % 10]} odeme")
    # kapsam dışı
    for d in range(25, 30):
        tx(tl, d, "OUT", 15000 * (d - 24), "Hesaplar arasi transfer", "TRANSFER")
    for d in range(10, 15):
        tx(tl, d, "OUT", 2500, "EFT masrafi", "FEE")
    tx(tl, 12, "OUT", 5000000, "Kredi taksiti", "LOAN")
    # eşleşmeyen
    for d in range(3):
        tx(tl, 30 + d, "IN", 123456 + d, f"Bilinmeyen gonderen {d}")
    # fatura iptal / ödenmiş
    tx(tl, 28, "IN", invs[29].total_kurus, f"{invs[29].invoice_no} iptal fatura")
    # doldur
    while len(txs) < 60:
        k = len(txs); tx(tl, 35 + k % 10, "IN", 100000 + k * 111, f"Rastgele giris {k}", "OTHER")
    # mükerrer kayıt (aynı dedup_key) -> import sırasında engellenir; seed'de tek kopya
    db.add_all(txs)
    db.add(m.AutomationSettings())
    db.commit(); db.close()
    print("Seed tamam:", len(accs), "hesap,", len(custs), "müşteri,", len(supps), "tedarikçi,",
          len(invs), "fatura,", len(txs), "banka hareketi")

if __name__ == "__main__":
    run()
