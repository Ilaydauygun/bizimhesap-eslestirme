import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getSettings, putSettings, getLogs, runMatching } from "../services/api";
import { fmtDateTime } from "../services/format";
import { useToast } from "../components/Toast";

const NUM = [["interval_minutes", "Çalışma sıklığı (dakika)"], ["min_score", "Minimum eşleşme puanı (0-100)"], ["date_tolerance_days", "Tarih toleransı (gün)"],
  ["w_amount", "Ağırlık: Tutar"], ["w_name", "Ağırlık: Cari ünvan"], ["w_invoice_no", "Ağırlık: Fatura no"], ["w_date", "Ağırlık: Tarih"]];

export default function AutomationSettings() {
  const toast = useToast();
  const s = useFetch(getSettings), logs = useFetch(getLogs);
  const [form, setForm] = useState(null);
  useEffect(() => { if (s.data && !form) setForm(s.data); }, [s.data]);  // yalnızca ilk yüklemede: yazılan değer ezilmez
  if (!form) return <div className="bh-alert">{s.error || "Yükleniyor…"}</div>;
  const save = async () => {
    const body = { enabled: form.enabled, auto_approve: form.auto_approve };
    NUM.forEach(([k]) => (body[k] = parseInt(form[k], 10)));
    try { await putSettings(body); toast.ok("Ayarlar kaydedildi."); s.reload(); } catch (e) { toast.err(e.userMessage); }
  };
  const run = async () => {
    try { const r = await runMatching(); toast.ok(`Çalıştırıldı: ${r.processed} hareket işlendi.`); s.reload(); logs.reload(); } catch (e) { toast.err(e.userMessage); }
  };
  return (
    <>
      <div className="row g-3">
        <div className="col-lg-7">
          <div className="bh-panel" style={{ marginTop: 0 }}><div className="bh-panel-h">Otomasyon Ayarları</div>
            <div className="bh-panel-b">
              <div className="form-check form-switch mb-2"><input className="form-check-input" type="checkbox" id="en" checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /><label htmlFor="en" className="form-check-label">Otomasyon açık</label></div>
              <div className="form-check form-switch mb-3"><input className="form-check-input" type="checkbox" id="aa" checked={form.auto_approve}
                onChange={(e) => setForm({ ...form, auto_approve: e.target.checked })} />
                <label htmlFor="aa" className="form-check-label">Otomatik onay (yalnızca tam tutar, doğrulanmış fatura no, skor ≥ 90 ve tek aday)</label></div>
              <div className="row g-2">{NUM.map(([k, l]) => (
                <div className="col-md-6" key={k}><label className="form-label small" htmlFor={k}>{l}</label>
                  <input id={k} type="number" className="form-control" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>))}</div>
              <p className="text-muted small mt-3 mb-2">{s.data.note}</p>
              <div className="d-flex gap-2"><button className="bh-btn green" onClick={save}>Kaydet</button>
                <button className="bh-btn match" onClick={run}><Play size={13} />Şimdi Çalıştır</button></div>
            </div></div>
        </div>
        <div className="col-lg-5">
          <div className="bh-panel" style={{ marginTop: 0 }}><div className="bh-panel-h">Durum</div>
            <div className="bh-panel-b"><table className="table table-sm mb-0"><tbody>
              <tr><th>Son çalışma</th><td>{fmtDateTime(s.data.last_run_at)}</td></tr>
              <tr><th>Sonraki çalışma</th><td>{s.data.next_run_at ? fmtDateTime(s.data.next_run_at) : "Planlı çalışma yok"}</td></tr>
              <tr><th>Başarılı işlem</th><td>{s.data.total_success}</td></tr><tr><th>Başarısız işlem</th><td>{s.data.total_fail}</td></tr></tbody></table></div></div>
        </div>
      </div>
      <div className="bh-panel"><div className="bh-panel-h">Otomasyon Günlüğü</div>
        <div className="bh-panel-b"><table className="bh-table"><thead><tr><th>Zaman</th><th>Tetikleyici</th><th>Başarılı</th><th>Başarısız</th><th>Mesaj</th></tr></thead>
          <tbody>{(logs.data || []).map((l) => <tr key={l.id}><td>{fmtDateTime(l.started_at)}</td>
            <td>{{ manual: "Manuel", scheduled: "Zamanlanmış", event: "Olay" }[l.trigger] || l.trigger}</td><td>{l.success}</td><td>{l.fail}</td><td>{l.message}</td></tr>)}
            {logs.data?.length === 0 && <tr><td colSpan={5} className="text-center text-muted">Henüz çalışma yok</td></tr>}</tbody></table></div></div>
    </>
  );
}
