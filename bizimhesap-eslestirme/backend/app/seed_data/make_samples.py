"""Örnek CSV/Excel dosyalarını üretir: python -m app.seed_data.make_samples"""
import csv, pathlib
import openpyxl

OUT = pathlib.Path(__file__).resolve().parents[3] / "sample_data"
IBAN_TL = "TR000000000000000000000001"
INV_H = ["fatura_no", "tur", "cari_unvan", "fatura_tarihi", "vade_tarihi", "tutar", "odenen", "para_birimi", "belge_tipi"]
INV = [
 ["SF-2026-101", "Satış", "Anadolu Yapı Ltd. Şti.", "01.11.2026", "30.11.2026", "12.000,00", "", "TRY", "Faturalaşmış"],
 ["SF-2026-102", "Satış", "Güneş Tekstil A.Ş.", "02.11.2026", "01.12.2026", "20.000,00", "", "TRY", "E-Faturalaşmış"],
 ["SF-2026-103", "Satış", "Çınar Gıda San. Tic. Ltd. Şti.", "03.11.2026", "03.12.2026", "3.500,00", "", "TRY", "Faturalaşmış"],
 ["SF-2026-104", "Satış", "Çınar Gıda San. Tic. Ltd. Şti.", "03.11.2026", "03.12.2026", "4.500,00", "", "TRY", "Faturalaşmış"],
 ["SF-2026-105", "Satış", "Ege Lojistik A.Ş.", "04.11.2026", "04.12.2026", "2.500,00", "", "TRY", "Faturalaşmış"],
 ["SF-2026-106", "Satış", "Ege Lojistik A.Ş.", "05.11.2026", "05.12.2026", "2.500,00", "", "TRY", "Faturalaşmış"],
 ["SF-2026-107", "Satış", "Yıldız Elektronik Ltd.", "05.11.2026", "05.12.2026", "9.000,00", "", "TRY", "Sipariş"],
 ["AF-2026-101", "Alış", "Marmara Kağıt A.Ş.", "01.11.2026", "30.11.2026", "4.200,00", "", "TRY", "Faturalaşmış"],
]
TX_H = ["tarih", "yon", "tutar", "para_birimi", "aciklama", "hesap_iban", "kategori"]
TX = [
 ["10.11.2026", "Giriş", "12.000,00", "TRY", "SF-2026-101 nolu fatura ANADOLU YAPI LTD", IBAN_TL, "Ödeme"],          # tam ödeme
 ["11.11.2026", "Giriş", "8.000,00", "TRY", "SF-2026-102 kısmi ödeme GÜNEŞ TEKSTİL", IBAN_TL, "Ödeme"],            # kısmi
 ["12.11.2026", "Giriş", "8.000,00", "TRY", "ÇINAR GIDA toplu ödeme SF-2026-103 SF-2026-104", IBAN_TL, "Ödeme"],  # toplu
 ["13.11.2026", "Giriş", "2.500,00", "TRY", "Ege Lojistik havale", IBAN_TL, "Ödeme"],                              # aynı tutarlı faturalar
 ["14.11.2026", "Çıkış", "4.200,00", "TRY", "AF-2026-101 Marmara Kağıt ödeme", IBAN_TL, "Ödeme"],                 # alış ödemesi
 ["15.11.2026", "Giriş", "5.000,00", "TRY", "Bilinmeyen gönderen", IBAN_TL, "Ödeme"],                              # eşleşmeyen
 ["16.11.2026", "Çıkış", "1.000,00", "TRY", "Hesaplar arası transfer", IBAN_TL, "Transfer"],                       # kapsam dışı
 ["10.11.2026", "Giriş", "12.000,00", "TRY", "SF-2026-101 nolu fatura ANADOLU YAPI LTD", IBAN_TL, "Ödeme"],        # mükerrer
]
BAD_INV = [["fatura_no", "tur", "tutar"], ["X-1", "Satış", "100"]]                                                  # zorunlu sütunlar eksik
BAD_TX = [TX_H] + [["31.31.2026", "Giriş", "100,00", "TRY", "geçersiz tarih", IBAN_TL, "Ödeme"],
                   ["10.11.2026", "Borç", "100,00", "TRY", "yön belirsiz", IBAN_TL, "Ödeme"],
                   ["10.11.2026", "Giriş", "yüz lira", "TRY", "geçersiz tutar", IBAN_TL, "Ödeme"],
                   ["10.11.2026", "Giriş", "100,00", "USD", "para birimi uyuşmuyor", IBAN_TL, "Ödeme"]]

def write_csv(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(header); w.writerows(rows)

def write_xlsx(name, header, rows):
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(header)
    for r in rows: ws.append(r)
    wb.save(OUT / name)

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for ext, fn in (("csv", write_csv), ("xlsx", write_xlsx)):
        fn(f"faturalar_ornek.{ext}", INV_H, INV); fn(f"banka_hareketleri_ornek.{ext}", TX_H, TX)
    write_csv("hatali_faturalar.csv", BAD_INV[0], BAD_INV[1:]); write_csv("hatali_hareketler.csv", BAD_TX[0], BAD_TX[1:])
    print("Örnek dosyalar:", sorted(p.name for p in OUT.iterdir()))
