import { useState } from "react";
import Modal from "./Modal";
import useFetch from "../hooks/useFetch";
import { getInvoices, manualMatch } from "../services/api";
import { fmtMoney, fmtDate, parseTRY, kurusToInput } from "../services/format";
import { useToast } from "./Toast";

const EXCLUDED = ["Sipariş", "İrsaliye", "İrsaliyeleşmiş"];

export default function ManualMatchModal({ tx, available, onClose, onDone }) {
  const toast = useToast();
  const { data } = useFetch(() => getInvoices({ kind: tx.direction === "IN" ? "SALE" : "PURCH" }), [tx.id]);
  const [sel, setSel] = useState({});
  const [busy, setBusy] = useState(false);
  const list = (data || []).filter((i) => i.currency === tx.currency && i.remaining_kurus > 0
    && i.status !== "İptal Edildi" && !EXCLUDED.includes(i.doc_type));
  const toggle = (i) => setSel((s) => {
    const n = { ...s };
    if (n[i.id] !== undefined) delete n[i.id];
    else n[i.id] = kurusToInput(Math.min(i.remaining_kurus, Math.max(available - Object.values(s).reduce((a, v) => a + (parseTRY(v) || 0), 0), 0)) || i.remaining_kurus);
    return n;
  });
  const total = Object.values(sel).reduce((a, v) => a + (parseTRY(v) || 0), 0);
  const bad = Object.entries(sel).some(([id, v]) => {
    const k = parseTRY(v), inv = list.find((x) => x.id === +id);
    return !k || k <= 0 || (inv && k > inv.remaining_kurus);
  }) || total > available || total === 0;
  const submit = async () => {
    setBusy(true);
    try {
      await manualMatch(tx.id, Object.entries(sel).map(([id, v]) => ({ invoice_id: +id, amount_kurus: parseTRY(v) })));
      toast.ok("Manuel eşleştirme kaydedildi."); onDone();
    } catch (e) { toast.err(e.userMessage); } finally { setBusy(false); }
  };
  return (
    <Modal title="Manuel Eşleştir" onClose={onClose} wide
      footer={<><button className="bh-btn dark" onClick={onClose}>Vazgeç</button>
        <button className="bh-btn green" disabled={bad || busy} onClick={submit}>Eşleştir ve Onayla</button></>}>
      <p>İşlem: <b>{tx.description}</b> — Kullanılabilir tutar: <b>{fmtMoney(available, tx.currency)}</b></p>
      <table className="bh-table">
        <thead><tr><th></th><th>Fatura No</th><th>{tx.direction === "IN" ? "Müşteri" : "Tedarikçi"}</th><th>Vade</th>
          <th className="num">Kalan</th><th className="num">Ayrılacak Tutar</th></tr></thead>
        <tbody>
          {list.map((i) => (
            <tr key={i.id}>
              <td><input type="checkbox" aria-label={`Seç ${i.invoice_no}`} checked={sel[i.id] !== undefined} onChange={() => toggle(i)} /></td>
              <td>{i.invoice_no}</td><td>{i.party}</td><td>{fmtDate(i.due_date)}</td>
              <td className="num">{fmtMoney(i.remaining_kurus, i.currency)}</td>
              <td className="num">{sel[i.id] !== undefined &&
                <input className="form-control form-control-sm text-end" style={{ width: 130, marginLeft: "auto" }} value={sel[i.id]}
                  aria-label={`Tutar ${i.invoice_no}`} onChange={(e) => setSel({ ...sel, [i.id]: e.target.value })} />}</td>
            </tr>
          ))}
          {list.length === 0 && <tr><td colSpan={6} className="text-center text-muted">Uygun fatura yok (yön, para birimi veya ödeme durumu).</td></tr>}
        </tbody>
      </table>
      <div className="mt-2">Toplam: <b>{fmtMoney(total, tx.currency)}</b>
        {total > available && <span className="text-danger"> — işlem tutarını aşıyor</span>}</div>
    </Modal>
  );
}
