"""Saf (DB'den bağımsız) kural tabanlı eşleştirme motoru.
Skor istatistiksel olasılık DEĞİL, kural tabanlı uygunluk puanıdır."""
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from rapidfuzz import fuzz
from app.utils.text import normalize_text, company_tokens, extract_invoice_numbers, norm_invoice_no

EXCLUDED_DOC_TYPES = {"Sipariş", "İrsaliye", "İrsaliyeleşmiş"}
STRONG, REVIEW = 90, 60

@dataclass
class Settings:
    w_amount: int = 40; w_name: int = 25; w_invoice_no: int = 25; w_date: int = 10
    date_tolerance_days: int = 30; min_score: int = 60; max_bulk: int = 5

@dataclass
class Tx:
    id: int; direction: str; category: str; description: str
    available_kurus: int; currency: str; tx_date: date

@dataclass
class Inv:
    id: int; invoice_no: str; kind: str; party_name: str; remaining_kurus: int
    currency: str; issue_date: date; due_date: date; cancelled: bool = False; doc_type: str = "Faturalaşmış"

@dataclass
class Candidate:
    allocations: dict[int, int]          # invoice_id -> kuruş
    score: int
    kind: str                            # FULL / PARTIAL / OVERPAY / BULK
    reasons: list[str] = field(default_factory=list)
    invoice_no_confirmed: bool = False

    @property
    def invoice_ids(self): return frozenset(self.allocations)

def is_eligible(tx: Tx, inv: Inv) -> bool:
    if tx.category != "PAYMENT" or tx.available_kurus <= 0: return False
    if (tx.direction, inv.kind) not in {("IN", "SALE"), ("OUT", "PURCH")}: return False
    if tx.currency != inv.currency: return False
    if inv.cancelled or inv.remaining_kurus <= 0 or inv.doc_type in EXCLUDED_DOC_TYPES: return False
    return True

def name_coverage(description: str, party: str) -> float:
    ptoks = company_tokens(party)
    dtoks = normalize_text(description).split()
    if not ptoks or not dtoks: return 0.0
    hits = sum(1 for p in ptoks if max(fuzz.ratio(p, d) for d in dtoks) >= 85)
    return hits / len(ptoks)

def date_factor(tx_date: date, inv: Inv, tol: int) -> float:
    d = min(abs((tx_date - inv.issue_date).days), abs((tx_date - inv.due_date).days))
    if d <= tol: return 1.0
    return max(0.0, 1 - (d - tol) / max(tol, 1))

def _score(s: Settings, f_amount, f_name, f_no, f_date) -> int:
    tot = s.w_amount + s.w_name + s.w_invoice_no + s.w_date
    raw = s.w_amount * f_amount + s.w_name * f_name + s.w_invoice_no * f_no + s.w_date * f_date
    return round(raw / tot * 100)

def _single(tx: Tx, inv: Inv, s: Settings, refs: set[str]) -> Candidate:
    reasons, alloc = [], min(tx.available_kurus, inv.remaining_kurus)
    if tx.available_kurus == inv.remaining_kurus:
        kind, f_amt = "FULL", 1.0; reasons.append("Tutar kalan fatura tutarıyla birebir aynı.")
    elif tx.available_kurus < inv.remaining_kurus:
        kind, f_amt = "PARTIAL", 0.5; reasons.append("Tutar kalan borçtan düşük: kısmi ödeme olarak değerlendirildi.")
    else:
        kind, f_amt = "OVERPAY", 0.3; reasons.append("Tutar kalan borçtan yüksek: fazla ödeme, inceleme gerekli.")
    cov = name_coverage(tx.description, inv.party_name)
    reasons.append(f"Ünvan benzerliği: %{round(cov*100)} ({inv.party_name}).")
    confirmed = norm_invoice_no(inv.invoice_no) in refs
    reasons.append("Fatura numarası açıklamada bulundu." if confirmed else "Açıklamada fatura numarası doğrulanamadı.")
    f_date = date_factor(tx.tx_date, inv, s.date_tolerance_days)
    reasons.append(f"Tarih uyumu: %{round(f_date*100)}.")
    return Candidate({inv.id: alloc}, _score(s, f_amt, cov, 1.0 if confirmed else 0.0, f_date), kind, reasons, confirmed)

def _bulk(tx: Tx, invs: list[Inv], s: Settings, refs: set[str]) -> list[Candidate]:
    out = []
    by_party: dict[str, list[Inv]] = {}
    for i in invs: by_party.setdefault(i.party_name, []).append(i)
    for party, lst in by_party.items():
        cov = name_coverage(tx.description, party)
        if cov < 0.5 and not any(norm_invoice_no(i.invoice_no) in refs for i in lst): continue
        lst = sorted(lst, key=lambda i: i.id)[:15]
        for n in range(2, s.max_bulk + 1):
            for combo in combinations(lst, n):
                if sum(i.remaining_kurus for i in combo) != tx.available_kurus: continue
                f_no = sum(norm_invoice_no(i.invoice_no) in refs for i in combo) / n
                f_date = sum(date_factor(tx.tx_date, i, s.date_tolerance_days) for i in combo) / n
                reasons = [f"Toplu ödeme: {n} faturanın kalan toplamı işlem tutarına eşit.",
                           f"Ünvan benzerliği: %{round(cov*100)} ({party}).",
                           f"Açıklamada {round(f_no*n)}/{n} fatura numarası bulundu.", f"Tarih uyumu: %{round(f_date*100)}."]
                out.append(Candidate({i.id: i.remaining_kurus for i in combo},
                                     _score(s, 1.0, cov, f_no, f_date), "BULK", reasons, f_no == 1.0))
    return out

def find_candidates(tx: Tx, invoices: list[Inv], s: Settings) -> list[Candidate]:
    elig = [i for i in invoices if is_eligible(tx, i)]
    refs = extract_invoice_numbers(tx.description)
    cands = [_single(tx, i, s, refs) for i in elig]
    cands += _bulk(tx, elig, s, refs)
    cands = [c for c in cands if c.score >= s.min_score]
    return sorted(cands, key=lambda c: (-c.score, sorted(c.invoice_ids)))

def decide(cands: list[Candidate]) -> dict:
    """Karar: kategori + otomatik onaya uygunluk (yalnız güvenli kurallarla)."""
    if not cands: return {"status": "UNMATCHED", "auto_ok": False, "ambiguous": False}
    strong = [c for c in cands if c.score >= STRONG]
    top = cands[0]
    ambiguous = len(strong) > 1 or (len(cands) > 1 and cands[1].score == top.score)
    confirmed = [c for c in cands if c.invoice_no_confirmed and c.kind == "FULL"]
    auto_ok = (top.kind == "FULL" and top.invoice_no_confirmed and top.score >= STRONG
               and len(strong) == 1 and len(confirmed) == 1 and not ambiguous)
    return {"status": "PENDING", "auto_ok": auto_ok, "ambiguous": ambiguous}
