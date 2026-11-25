import re
from decimal import Decimal, ROUND_HALF_UP

def to_kurus(value) -> int:
    """Decimal/str -> tam sayı kuruş. float kabul edilmez."""
    if isinstance(value, float):
        raise TypeError("Finansal değerlerde float kullanılamaz.")
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def parse_tr_amount(text: str) -> int:
    """'1.234,56' -> 123456 kuruş."""
    t = str(text).strip().replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", t):   # 1.500 -> 1500 (Türkçe binlik ayracı)
        t = t.replace(".", "")
    return to_kurus(Decimal(t))

def fmt_tr(kurus: int) -> str:
    s = f"{abs(kurus)/100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if kurus < 0 else "") + s
