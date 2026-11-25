import { useMemo, useState } from "react";
import { Play, Upload, Check, X, Link2, Eye, Undo2, FileSpreadsheet } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getStats, getTransactions, getAccounts, getResults, runMatching, approveMatch, rejectMatch, undoMatch, exportUrl } from "../services/api";
import { fmtMoney, fmtDate } from "../services/format";
import StatusBadge from "../components/StatusBadge";
import TxDetailModal from "../components/TxDetailModal";
import ManualMatchModal from "../components/ManualMatchModal";
import ImportModal from "../components/ImportModal";
import { useToast } from "../components/Toast";

const CARDS = [
  ["total", "Toplam Banka Hareketi", "#337ab7"], ["matched", "Eşleşen İşlemler", "#5bb55b"],
  ["pending", "Onay Bekleyen İşlemler", "#f0c33c"], ["unmatched", "Eşleşmeyen İşlemler", "#d6524e"],
  ["partial", "Kısmi Ödemeler", "#48a9ba"], ["match_rate", "Eşleşme Oranı", "#6c5ce7"],
];

export default function Reconciliation() {
  const toast = useToast();
  const stats = useFetch(getStats), txs = useFetch(getTransactions), accs = useFetch(getAccounts), res = useFetch(getResults);
  const [f, setF] = useState({ status: "", q: "", dir: "" });
  const [modal, setModal] = useState(null);
  const [busy, setBusy] = useState(false);
  const reload = () => { stats.reload(); txs.reload(); res.reload(); };
  const accName = (id) => accs.data?.find((a) => a.id === id)?.name || id;
  const byTx = useMemo(() => {
    const m = {};
    (res.data || []).forEach((x) => (m[x.transaction_id] ||= []).push(x));
    return m;
  }, [res.data]);
  const rows = (txs.data || []).filter((t) => (!f.status || t.status === f.status) && (!f.dir || t.direction === f.dir)
    && (!f.q || t.description.toLowerCase().includes(f.q.toLowerCase())));
  const act = async (fn, okMsg) => { try { await fn(); toast.ok(okMsg); reload(); } catch (e) { toast.err(e.userMessage); } };
  const start = async () => {
    setBusy(true);
    try { const r = await runMatching(); toast.ok(`Eşleştirme tamamlandı: ${r.processed} hareket işlendi, ${r.failed} hata.`); reload(); }
    catch (e) { toast.err(e.userMessage); } finally { setBusy(false); }
  };
  const availableOf = (t) => t.amount_kurus - (byTx[t.id] || []).filter((x) => x.status === "APPROVED")
    .reduce((a, x) => a + x.allocations.reduce((s, y) => s + y.amount_kurus, 0), 0);

  return (
    <>
      <div className="d-flex flex-wrap gap-2 mb-3">
        <button className="bh-btn match" disabled={busy} onClick={start}><Play size={14} />Otomatik Eşleştirmeyi Başlat</button>
        <button className="bh-btn green" onClick={() => setModal({ type: "txup" })}><Upload size={14} />Banka Hareketi Yükle</button>
        <button className="bh-btn info" onClick={() => setModal({ type: "invup" })}><Upload size={14} />Fatura Yükle</button>
        <button className="bh-btn teal" onClick={() => (window.location.href = exportUrl("xlsx"))}><FileSpreadsheet size={14} />Excel'e Aktar</button>
        <button className="bh-btn dark" onClick={() => (window.location.href = exportUrl("csv"))}>CSV'ye Aktar</button>
      </div>
      {(stats.error || txs.error) && <div className="bh-alert">{stats.error || txs.error}</div>}
      <div className="row g-3 mb-2">
        {CARDS.map(([k, l, c]) => (
          <div className="col-6 col-lg-2" key={k}><div className="bh-stat" style={{ "--c": c }}>
            <div className="v" data-testid={`stat-${k}`}>{stats.data ? (k === "match_rate" ? `%${stats.data[k]}` : stats.data[k]) : "–"}</div>
            <div className="l">{l}</div></div></div>
        ))}
      </div>
      <div className="bh-panel">
        <div className="bh-panel-h">Banka Hareketleri ve Eşleşmeler</div>
        <div className="bh-panel-b">
          <div className="d-flex flex-wrap gap-2 mb-2">
            <select className="form-select w-auto" aria-label="Durum filtresi" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
              <option value="">Tüm Durumlar</option><option value="MATCHED">Eşleşti</option><option value="PENDING">Onay Bekliyor</option>
              <option value="UNMATCHED">Eşleşmedi</option><option value="PARTIAL">Kısmi Eşleşme</option><option value="OUT_OF_SCOPE">Kapsam Dışı</option>
            </select>
            <select className="form-select w-auto" aria-label="Yön filtresi" value={f.dir} onChange={(e) => setF({ ...f, dir: e.target.value })}>
              <option value="">Giriş ve Çıkış</option><option value="IN">Para Girişi</option><option value="OUT">Para Çıkışı</option></select>
            <input className="form-control w-auto" placeholder="Açıklamada ara…" aria-label="Ara" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="bh-table">
              <thead><tr><th>İşlem Tarihi</th><th>Banka Hesabı</th><th>İşlem Türü</th><th>Açıklama</th><th className="num">Tutar</th>
                <th>Para Birimi</th><th>Eşleşen Fatura</th><th>Müşteri / Tedarikçi</th><th>Skor</th><th>Durum</th><th>İşlemler</th></tr></thead>
              <tbody>
                {rows.map((t) => {
                  const ms = byTx[t.id] || [], sug = ms.find((x) => x.status === "SUGGESTED"), appr = ms.filter((x) => x.status === "APPROVED");
                  const shown = appr.length ? appr : sug ? [sug] : [];
                  const allocs = shown.flatMap((x) => x.allocations);
                  const open = t.category === "PAYMENT" && t.status !== "MATCHED";
                  return (
                    <tr key={t.id} data-testid={`row-${t.id}`}>
                      <td>{fmtDate(t.date)}</td><td>{accName(t.account_id)}</td>
                      <td>{t.direction === "IN" ? "Para Girişi" : "Para Çıkışı"}</td><td>{t.description}</td>
                      <td className="num">{fmtMoney(t.amount_kurus, t.currency)}</td><td>{t.currency}</td>
                      <td>{allocs.map((a) => a.invoice_no).join(", ") || "–"}</td>
                      <td>{[...new Set(allocs.map((a) => a.party))].join(", ") || "–"}</td>
                      <td>{shown[0] ? shown[0].score || "manuel" : "–"}</td>
                      <td><StatusBadge status={t.status} /></td>
                      <td className="text-nowrap">
                        <button className="bh-btn green" title="Eşleşmeyi Onayla" aria-label={`Onayla ${t.id}`} disabled={!sug}
                          onClick={() => act(() => approveMatch(sug.match_id), "Eşleşme onaylandı.")}><Check size={12} /></button>{" "}
                        <button className="bh-btn red" title="Eşleşmeyi Reddet" aria-label={`Reddet ${t.id}`} disabled={!sug}
                          onClick={() => window.confirm("Bu öneri reddedilsin mi?") && act(() => rejectMatch(sug.match_id), "Öneri reddedildi.")}><X size={12} /></button>{" "}
                        <button className="bh-btn orange" title="Manuel Eşleştir" aria-label={`Manuel ${t.id}`} disabled={!open}
                          onClick={() => setModal({ type: "manual", tx: t })}><Link2 size={12} /></button>{" "}
                        <button className="bh-btn info" title="Detay Görüntüle" aria-label={`Detay ${t.id}`}
                          onClick={() => setModal({ type: "detail", tx: t })}><Eye size={12} /></button>{" "}
                        <button className="bh-btn dark" title="Eşleşmeyi Geri Al" aria-label={`Geri al ${t.id}`} disabled={!appr.length}
                          onClick={() => window.confirm("Onaylı eşleşme geri alınsın mı? Fatura ödeme durumu yeniden hesaplanır.") &&
                            act(() => undoMatch(appr[appr.length - 1].match_id), "Eşleşme geri alındı.")}><Undo2 size={12} /></button>
                      </td>
                    </tr>);
                })}
                {rows.length === 0 && <tr><td colSpan={11} className="text-center text-muted">Eşleşen kayıt bulunamadı</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      {modal?.type === "detail" && <TxDetailModal tx={modal.tx} accountName={accName(modal.tx.account_id)}
        matches={byTx[modal.tx.id] || []} onClose={() => setModal(null)} onChanged={reload} />}
      {modal?.type === "manual" && <ManualMatchModal tx={modal.tx} available={availableOf(modal.tx)}
        onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
      {modal?.type === "txup" && <ImportModal title="Banka Hareketi Yükle" path="/bank-transactions/import" onClose={() => setModal(null)} onDone={reload}
        hint="Sütunlar: tarih; yon (Giriş/Çıkış); tutar; para_birimi; aciklama; hesap_iban; kategori (isteğe bağlı). Yüklenen hareketler için eşleştirme otomatik çalışır." />}
      {modal?.type === "invup" && <ImportModal title="Fatura Yükle" path="/invoices/import" onClose={() => setModal(null)} onDone={reload}
        hint="Sütunlar: fatura_no; tur (Satış/Alış); cari_unvan; fatura_tarihi; vade_tarihi; tutar; para_birimi; odenen ve belge_tipi isteğe bağlı." />}
    </>
  );
}
