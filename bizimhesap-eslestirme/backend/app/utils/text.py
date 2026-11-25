import re, unicodedata

_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "ç": "c", "ğ": "g", "ö": "o", "ş": "s", "ü": "u",
                     "Ç": "c", "Ğ": "g", "Ö": "o", "Ş": "s", "Ü": "u"})
LEGAL = {"ltd", "sti", "as", "a", "s", "limited", "sirketi", "anonim", "san", "tic", "ve", "sanayi",
         "ticaret", "ic", "dis", "inc", "gmbh", "co", "corp", "llc"}

def normalize_text(s: str) -> str:
    """Türkçe karakterleri sadeleştirir, küçük harfe çevirir, noktalama/boşluk temizler."""
    s = (s or "").translate(_TR).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def company_tokens(name: str) -> list[str]:
    return [t for t in normalize_text(name).split() if t not in LEGAL]

_INV_RE = re.compile(r"\b[A-Z]{1,5}[-/]?\d{4}[-/]\d{2,}\b|\b[A-Z]{2,5}[-/]?\d{3,}\b")

def norm_invoice_no(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").translate(_TR).upper())

def extract_invoice_numbers(description: str) -> set[str]:
    up = (description or "").translate(_TR).upper()
    return {norm_invoice_no(m) for m in _INV_RE.findall(up)}
