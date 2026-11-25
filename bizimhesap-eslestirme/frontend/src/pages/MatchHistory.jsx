import { useState } from "react";
import { Undo2 } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getHistory, getAuditLogs, undoMatch } from "../services/api";
import { fmtMoney, fmtDate, fmtDateTime, MATCH_STATUS } from "../services/format";
import { useToast } from "../components/Toast";

export default function MatchHistory() {
  const toast = useToast();
  const [tab, setTab] = useState("matches");
  const h = useFetch(getHistory), a = useFetch(getAuditLogs);
  const undo = async (id) => {
    if (!window.confirm("Onaylı eşleşme geri alınsın mı?")) return;
    try { await undoMatch(id); toast.ok("Eşleşme geri alındı."); h.reload(); a.reload(); } catch (e) { toast.err(e.userMessage); }
  };
  return (
    <div className="bh-panel" style={{ marginTop: 0 }}>
      <div className="bh-panel-h">Eşleşme Geçmişi</div>
      <div className="bh-panel-b">
        <div className="btn-group mb-3">
          <button className={`btn btn-sm ${tab === "matches" ? "btn-dark" : "btn-outline-dark"}`} onClick={() => setTab("matches")}>Kararlar</button>
          <button className={`btn btn-sm ${tab === "audit" ? "btn-dark" : "btn-outline-dark"}`} onClick={() => setTab("audit")}>Denetim Kaydı</button></div>
        {(h.error || a.error) && <div className="bh-alert">{h.error || a.error}</div>}
        {tab === "matches" ? (
          <table className="bh-table"><thead><tr><th>Karar Zamanı</th><th>İşlem Tarihi</th><th>Açıklama</th><th className="num">İşlem Tutarı</th><th>Faturalar</th><th>Skor</th><th>Durum</th><th></th></tr></thead>
            <tbody>
              {(h.data || []).map((x) => (
                <tr key={x.match_id}><td>{fmtDateTime(x.decided_at)}</td><td>{fmtDate(x.tx_date)}</td><td>{x.tx_description}</td>
                  <td className="num">{fmtMoney(x.tx_amount_kurus)}</td><td>{x.allocations.map((y) => `${y.invoice_no} (${fmtMoney(y.amount_kurus)})`).join(", ")}</td>
                  <td>{x.score || "manuel"}</td><td>{MATCH_STATUS[x.status]}</td>
                  <td>{x.status === "APPROVED" && <button className="bh-btn dark" aria-label={`Geri al ${x.match_id}`} onClick={() => undo(x.match_id)}><Undo2 size={12} />Geri Al</button>}</td></tr>))}
              {h.data?.length === 0 && <tr><td colSpan={8} className="text-center text-muted">Henüz karar yok</td></tr>}
            </tbody></table>
        ) : (
          <table className="bh-table"><thead><tr><th>Zaman</th><th>İşlem</th><th>Varlık</th><th>Kayıt</th><th>Ayrıntı</th></tr></thead>
            <tbody>{(a.data || []).map((x, i) => <tr key={i}><td>{fmtDateTime(x.at)}</td><td>{x.action}</td><td>{x.entity}</td><td>{x.entity_id ?? "–"}</td><td>{x.detail}</td></tr>)}</tbody></table>
        )}
      </div>
    </div>
  );
}
