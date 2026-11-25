// Gerçek backend'e (localhost:8000, seed'li SQLite) karşı arayüz testleri. Sıra önemlidir: durum paylaşılır.
import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import { ToastProvider } from "../components/Toast";
import { parseTRY, kurusToDecimalStr } from "../services/format";

const show = (path) => render(<MemoryRouter initialEntries={[path]}><ToastProvider><App /></ToastProvider></MemoryRouter>);
const stat = (k) => screen.getByTestId(`stat-${k}`);
const user = userEvent.setup();
beforeAll(() => { vi.spyOn(window, "confirm").mockReturnValue(true); });

describe("para biçimi", () => {
  it("Türkçe tutarları kuruşa çevirir", () => {
    expect(parseTRY("1.234,56")).toBe(123456); expect(parseTRY("1.500")).toBe(150000); expect(parseTRY("abc")).toBeNull();
    expect(kurusToDecimalStr(5)).toBe("0.05");
  });
});

describe("Banka-Fatura Eşleştirme", () => {
  it("özet kartlarını backend'den yükler", async () => {
    show("/nakit/eslestirme");
    await waitFor(() => expect(stat("total")).toHaveTextContent("60"));
    expect(screen.getAllByRole("row").length).toBeGreaterThan(60);
  });

  it("otomatik eşleştirmeyi başlatır, onay bekleyenler oluşur", async () => {
    show("/nakit/eslestirme");
    await waitFor(() => expect(stat("total")).toHaveTextContent("60"));
    await user.click(screen.getByRole("button", { name: /Otomatik Eşleştirmeyi Başlat/ }));
    expect(await screen.findByText(/Eşleştirme tamamlandı/)).toBeInTheDocument();
    await waitFor(() => expect(Number(stat("pending").textContent)).toBeGreaterThan(0));
  });

  it("öneriyi onaylar ve geri alır", async () => {
    show("/nakit/eslestirme");
    await waitFor(() => expect(Number(stat("pending").textContent)).toBeGreaterThan(0));
    let ok;
    await waitFor(() => { ok = screen.queryAllByRole("button", { name: /^Onayla \d+$/ }).find((b) => !b.disabled); expect(ok).toBeTruthy(); });
    const id = ok.getAttribute("aria-label").split(" ")[1];
    await user.click(ok);
    expect(await screen.findByText("Eşleşme onaylandı.")).toBeInTheDocument();
    await waitFor(() => expect(stat("matched")).toHaveTextContent("1"));
    await waitFor(() => expect(within(screen.getByTestId(`row-${id}`)).queryByText("Onay Bekliyor")).toBeNull());
    expect(within(screen.getByTestId(`row-${id}`)).getByText(/Eşleşti|Kısmi Eşleşme/)).toBeInTheDocument();
    // aynı satırda onay artık pasif, geri al aktif
    expect(screen.getByRole("button", { name: `Onayla ${id}` })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: `Geri al ${id}` }));
    expect(await screen.findByText("Eşleşme geri alındı.")).toBeInTheDocument();
    await waitFor(() => expect(stat("matched")).toHaveTextContent("0"));
  });

  it("öneriyi reddeder", async () => {
    show("/nakit/eslestirme");
    await waitFor(() => expect(Number(stat("pending").textContent)).toBeGreaterThan(0));
    const before = Number(stat("pending").textContent);
    let rj;
    await waitFor(() => { rj = screen.queryAllByRole("button", { name: /^Reddet \d+$/ }).find((b) => !b.disabled); expect(rj).toBeTruthy(); });
    await user.click(rj);
    expect(await screen.findByText("Öneri reddedildi.")).toBeInTheDocument();
    await waitFor(() => expect(Number(stat("pending").textContent)).toBe(before - 1));
  });

  it("detay ekranında banka hareketi ve aday faturaları gerekçeleriyle gösterir", async () => {
    show("/nakit/eslestirme");
    await waitFor(() => expect(Number(stat("pending").textContent)).toBeGreaterThan(0));
    const badge = (await screen.findAllByText("Onay Bekliyor", { selector: "span.st" }))[0];
    await user.click(within(badge.closest("tr")).getByRole("button", { name: /^Detay \d+$/ }));
    const dlg = await screen.findByRole("dialog", { name: "Eşleşme Detayı" });
    expect(within(dlg).getByText("Banka Hareketi")).toBeInTheDocument();
    await waitFor(() => expect(within(dlg).getAllByTestId("candidate").length).toBeGreaterThan(0));
    expect(within(dlg).getByText(/olasılık değil/)).toBeInTheDocument();
  });

  it("manuel eşleştirir (kısmi ödeme) ve fatura kalan borcu düşer", async () => {
    show("/nakit/eslestirme");
    await waitFor(() => expect(stat("total")).toHaveTextContent("60"));
    const row = (await screen.findByText("Bilinmeyen gonderen 0")).closest("tr");
    await user.click(within(row).getByRole("button", { name: /^Manuel \d+$/ }));
    const dlg = await screen.findByRole("dialog", { name: "Manuel Eşleştir" });
    const box = (await within(dlg).findAllByRole("checkbox"))[0];
    await user.click(box);
    await user.click(within(dlg).getByRole("button", { name: "Eşleştir ve Onayla" }));
    expect(await screen.findByText("Manuel eşleştirme kaydedildi.")).toBeInTheDocument();
    await waitFor(() => expect(within(screen.getByText("Bilinmeyen gonderen 0").closest("tr")).getByText("Eşleşti")).toBeInTheDocument());
  });

  it("hatalı dosyada satır hatalarını gösterir", async () => {
    show("/nakit/eslestirme");
    await user.click(await screen.findByRole("button", { name: /Banka Hareketi Yükle/ }));
    const dlg = await screen.findByRole("dialog");
    const csv = "tarih;yon;tutar;para_birimi;aciklama;hesap_iban\n31.31.2026;Giriş;100,00;TRY;x;TR000000000000000000000001\n";
    await user.upload(within(dlg).getByLabelText("Dosya seç"), new File([csv], "t.csv", { type: "text/csv" }));
    await user.click(within(dlg).getByRole("button", { name: "Yükle" }));
    expect(await within(dlg).findByText(/1 satır hatalı/)).toBeInTheDocument();
    expect(within(dlg).getByText(/Geçersiz tarih/)).toBeInTheDocument();
  });
});

describe("diğer sayfalar", () => {
  it("geçmiş sayfası kararları listeler", async () => {
    show("/nakit/gecmis");
    expect(await screen.findByText("Geri Alındı")).toBeInTheDocument();
    expect(screen.getByText("Reddedildi")).toBeInTheDocument();
  });

  it("otomasyon ayarlarını kaydeder, geçersiz değeri API reddeder", async () => {
    show("/nakit/otomasyon");
    const score = await screen.findByLabelText(/Minimum eşleşme puanı/);
    await user.clear(score); await user.type(score, "70");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Ayarlar kaydedildi.")).toBeInTheDocument();
    const iv = screen.getByLabelText(/Çalışma sıklığı/);
    await user.clear(iv); await user.type(iv, "0");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText(/Geçersiz istek/)).toBeInTheDocument();
    expect(screen.getAllByText("Manuel").length).toBeGreaterThan(0);   // günlükte manuel çalışma
  });

  it("satış faturası oluşturur", async () => {
    show("/satislar");
    await screen.findByText("SF-2026-001");
    await user.click(screen.getByRole("button", { name: /Yeni Satış Faturası/ }));
    const dlg = await screen.findByRole("dialog");
    await user.type(within(dlg).getByLabelText("Fatura No"), "SF-TEST-1");
    await user.type(within(dlg).getByLabelText("Cari ünvan"), "Test Müşteri A.Ş.");
    await user.type(within(dlg).getByLabelText("Tutar"), "1.250,50");
    await user.click(within(dlg).getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Fatura oluşturuldu.")).toBeInTheDocument();
    expect(await screen.findByText("SF-TEST-1")).toBeInTheDocument();
  });

  it("hesap ekranından para girişi kaydeder, mükerrerini reddeder", async () => {
    show("/nakit/hesaplarim");
    const openBtn = async () => { const b = await screen.findByRole("button", { name: /Hesaba Para Girişi Yap/ }); await waitFor(() => expect(b).toBeEnabled()); await user.click(b); };
    await openBtn();
    for (let i = 0; i < 2; i++) {
      const dlg = await screen.findByRole("dialog");
      await user.clear(within(dlg).getByLabelText("Tutar")); await user.type(within(dlg).getByLabelText("Tutar"), "321,00");
      await user.clear(within(dlg).getByLabelText("Açıklama")); await user.type(within(dlg).getByLabelText("Açıklama"), "arayüz testi girişi");
      await user.click(within(dlg).getByRole("button", { name: "Kaydet" }));
      if (i === 0) {
        expect(await screen.findByText("Hareket kaydedildi.")).toBeInTheDocument();
        await openBtn();
      } else {
        expect(await screen.findByText(/mükerrer/)).toBeInTheDocument();
      }
    }
  });
});

describe("hata yönetimi", () => {
  it("beklenmeyen render hatasında beyaz ekran yerine hata mesajı gösterir", async () => {
    const { default: ErrorBoundary } = await import("../components/ErrorBoundary");
    const Bomb = () => { throw new Error("deneme hatası"); };
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary><Bomb /></ErrorBoundary>);
    expect(await screen.findByText("Bir hata oluştu")).toBeInTheDocument();
    expect(screen.getByText(/deneme hatası/)).toBeInTheDocument();
  });
});

describe("beklenmeyen sunucu cevabı", () => {
  it("boş veya JSON olmayan cevabı başarılı gibi göstermez, cevabı gösterir", async () => {
    const api = (await import("../services/api")).default;
    const spy = vi.spyOn(api, "post").mockResolvedValue({ data: "<!doctype html><title>x</title>", status: 200, headers: { "content-type": "text/html" } });
    show("/nakit/eslestirme");
    await user.click(await screen.findByRole("button", { name: /Banka Hareketi Yükle/ }));
    const dlg = await screen.findByRole("dialog");
    await user.upload(within(dlg).getByLabelText("Dosya seç"), new File(["a"], "t.csv"));
    await user.click(within(dlg).getByRole("button", { name: "Yükle" }));
    expect(await within(dlg).findByText(/beklenmeyen bir cevap/)).toBeInTheDocument();
    expect(within(dlg).getByText(/doctype html/)).toBeInTheDocument();
    expect(within(dlg).queryByText(/kayıt aktarıldı/)).toBeNull();
    spy.mockRestore();
  });
});
