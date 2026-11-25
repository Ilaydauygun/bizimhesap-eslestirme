# Otomatik Banka Hareketleri ve Fatura Eşleştirme Modülü (Prototip)

Kural tabanlı, deterministik, denetlenebilir. Yapay zekâ/LLM kullanılmaz. Gerçek Bizim Hesap entegrasyonu yoktur;
`LocalDataProvider` (SQLite + sentetik veri) ile çalışır, `BizimHesapDataProvider` ileride resmi API ile yazılacaktır.

## Hızlı başlangıç (Windows)
1. Python 3.11+ ve Node.js 18+ kurulu olmalı.
2. `kurulum.bat` dosyasına çift tıklayın (sanal ortam, bağımlılıklar, örnek veri, npm install).
3. `calistir.bat` dosyasına çift tıklayın. Arayüz: http://localhost:5173 — API dokümantasyonu: http://localhost:8000/docs
(Mac/Linux: `./kurulum.sh` sonra `./calistir.sh`)

## Durum (1.–4. Gün tamam)
- [x] Klasör yapısı, SQLAlchemy modelleri (10 tablo), kuruş (int) tabanlı para yardımcıları
- [x] Sentetik veri: 3 hesap, 15 müşteri, 10 tedarikçi, 30 satış + 20 alış faturası, 60 hareket
- [x] GET: /api/bank-accounts, /api/bank-transactions, /api/invoices, /api/dashboard/stats
- [x] Eşleştirme motoru (normalizasyon, RapidFuzz skorlama, karar kuralları, kısmi/toplu/fazla ödeme)
- [x] Onay / ret / geri alma / manuel eşleştirme (tek transaction, atomik durum geçişi), audit log, çalışma kilidi
- [x] 29 Pytest testi (çalıştırıldı, geçti)
- [x] CSV/Excel import (banka hareketi + fatura), manuel kayıt, mükerrer koruması, satır bazlı hata raporu
- [x] APScheduler (varsayılan 15 dk, tek örnek), olay tabanlı tetikleme, ayarlar/log/geçmiş endpoint'leri, Excel/CSV rapor
- [x] React + Bootstrap 5 arayüz (Bizim Hesap görünümü), tüm eşleştirme butonları API'ye bağlı: otomatik eşleştirme, onay/ret/geri alma, manuel eşleştirme, detay (banka hareketi + aday faturalar + gerekçeler), dosya yükleme, rapor indirme, ayarlar, geçmiş, günlük
- [x] 12 arayüz testi (jsdom, gerçek backend'e karşı çalıştırıldı, geçti)
- [ ] Veri sağlayıcı adapter'ları (LocalDataProvider/BizimHesapDataProvider), ER/mimari diyagramları, sunum notları, entegrasyon yol haritası, Müşteriler/Tedarikçiler listeleri

## Windows (VS Code, PowerShell) kurulum
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH="."
python -m app.seed_data.seed
uvicorn app.main:app --reload
```
Swagger: http://localhost:8000/docs

## Frontend
```powershell
cd frontend
npm install
npm run dev
```
http://localhost:5173 (API istekleri 8000 portuna yönlendirilir)

## Test
```powershell
cd backend
$env:PYTHONPATH="."
pytest app/tests -q
```

## Örnek veri
`python -m app.seed_data.make_samples` ile `sample_data/` altında örnek ve hatalı CSV/XLSX dosyaları üretilir.
Sıra: `python -m app.seed_data.seed` → API'yi başlat → önce `faturalar_ornek.csv`, sonra `banka_hareketleri_ornek.csv` yükle (Swagger: /docs).

## Bilinen sınırlar
- Mükerrer anahtarı: hesap + tarih + yön + tutar + açıklama (+ opsiyonel `referans`). Aynı gün aynı tutar ve açıklamayla gelen iki gerçek hareketi ayırt etmek için `referans` sütunu kullanılmalı.
- SQLite tek yazıcıya izin verir; yüksek eş zamanlılık için PostgreSQL'e geçiş gerekir.
- Zamanlayıcı süreç içidir; birden fazla uvicorn worker'ı ile çalıştırılmamalıdır.

## Arayüz testleri
Backend'i seed'li veritabanıyla başlatın, sonra:
```powershell
cd backend; $env:DISABLE_SCHEDULER="1"; python -m app.seed_data.seed; uvicorn app.main:app --port 8000
# ikinci terminal
cd frontend; npm test
```
Testler veriyi değiştirir (onay, ret, fatura oluşturma); her çalıştırmadan önce seed'i yeniden çalıştırın.
