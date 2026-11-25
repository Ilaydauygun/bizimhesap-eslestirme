import Modal from "./Modal";
import useFetch from "../hooks/useFetch";
import { getCandidates, manualMatch, approveMatch, rejectMatch } from "../services/api";
import { fmtMoney, fmtDate, KIND } from "../services/format";
import StatusBadge from "./StatusBadge";
import { useToast } from "./Toast";

export default function TxDetailModal({ tx, accountName, matches, onClose, onChanged }) {
  const toast = useToast();
  const { data, error } = useFetch(() => getCandidates(tx.id), [tx.id]);
  const sug = matches.find((x) => x.status === "SUGGESTED");
  const appr = matches.filter((x) => x.status === "APPROVED");
  const run = async (fn, msg) => { try { await fn(); toast.ok(msg); onChanged(); onClose(); } catch (e) { toast.err(e.userMessage); } };
  return (
    <Modal title="Eşleşme Detayı" onClose={onClose} wide
      footer={<>
        {sug && <button className="bh-btn red" onClick={() => run(() => rejectMatch(sug.match_id), "Öneri reddedildi.")}>Eşleşmeyi Reddet</button>}
        {sug && <button className="bh-btn green" onClick={() => run(() => approveMatch(sug.match_id), "Eşleşme onaylandı.")}>Eşleşmeyi Onayla</button>}
        <button className="bh-btn dark" onClick={onClose}>Kapat</button></>}>
      <div className="row g-3">
        <div className="col-md-4">
          <h6>Banka Hareketi</h6>
          <table className="table table-sm"><tbody>
            <tr><th>Tarih</th><td>{fmtDate(tx.date)}</td></tr><tr><th>Hesap</th><td>{accountName}</td></tr>
            <tr><th>Yön</th><td>{tx.direction === "IN" ? "Para Girişi" : "Para Çıkışı"}</td></tr>
            <tr><th>Tutar</th><td>{fmtMoney(tx.amount_kurus, tx.currency)}</td></tr>
            <tr><th>Açıklama</th><td>{tx.description}</td></tr>
            <tr><th>Durum</th><td><StatusBadge status={tx.status} /></td></tr></tbody></table>
          {appr.length > 0 && <div className="alert alert-success small">Onaylı: {appr.map((a) => a.allocations.map((x) => x.invoice_no).join(", ")).join(" | ")}</div>}
        </div>
        <div className="col-md-8">
          <h6>Aday Faturalar ve Eşleştirme Gerekçeleri</h6>
          {error && <div className="alert alert-danger">{error}</div>}
          {data && <p className="text-muted small">{data.note}</p>}
          {data && data.candidates.length === 0 && <div className="alert alert-warning">Kurallara uyan aday fatura bulunamadı.</div>}
          {(data?.candidates || []).map((c, idx) => (
            <div key={idx} className="border rounded p-2 mb-2" data-testid="candidate">
              <div className="d-flex justify-content-between align-items-center">
                <div><b>Skor: {c.score}</b> / 100 — {KIND[c.kind]}{c.invoice_no_confirmed && " — fatura no doğrulandı"}</div>
                <button className="bh-btn orange" disabled={tx.status === "MATCHED"}
                  onClick={() => run(() => manualMatch(tx.id, c.allocations.map((a) => ({ invoice_id: a.invoice_id, amount_kurus: a.amount_kurus }))), "Aday ile eşleştirildi ve onaylandı.")}>
                  Bu adayla eşleştir</button>
              </div>
              <table className="table table-sm my-2"><thead><tr><th>Fatura</th><th>Cari</th><th>Vade</th><th className="text-end">Fatura Kalan</th><th className="text-end">Ayrılacak</th></tr></thead>
                <tbody>{c.allocations.map((a) => (
                  <tr key={a.invoice_id}><td>{a.invoice_no}</td><td>{a.party}</td><td>{fmtDate(a.due_date)}</td>
                    <td className="text-end">{fmtMoney(a.remaining_kurus, a.currency)}</td><td className="text-end">{fmtMoney(a.amount_kurus, a.currency)}</td></tr>))}</tbody></table>
              <ul className="small mb-0">{c.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          ))}
        </div>
      </div>
    </Modal>
  );
}
