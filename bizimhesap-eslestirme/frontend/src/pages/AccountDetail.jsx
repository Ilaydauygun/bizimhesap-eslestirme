import { useMemo, useState } from "react";
import { ArrowDownToLine, ArrowUpFromLine, ArrowRightLeft, Pencil, FileText, Wand2 } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getAccounts, getTransactions, getResults, runMatching, createTransaction } from "../services/api";
import { fmtMoney, fmtDate, parseTRY, kurusToDecimalStr } from "../services/format";
import StatusBadge from "../components/StatusBadge";
import Modal from "../components/Modal";
import TxDetailModal from "../components/TxDetailModal";
import { useToast } from "../components/Toast";

function MoneyModal({ account, direction, onClose, onDone }) {
  const toast = useToast();
  const [f, setF] = useState({ date: new Date().toISOString().slice(0, 10), amount: "", description: "" });
  const k = parseTRY(f.amount);
  const submit = async () => {
    try {
      await createTransaction({ account_id: account.id, date: f.date, direction, amount: kurusToDecimalStr(k), description: f.description });
      toast.ok("Hareket kaydedildi."); onDone();
    } catch (e) { toast.err(e.userMessage); }
  };
  return (
    <Modal title={direction === "IN" ? "Hesaba Para Girişi" : "Hesaptan Para Çıkışı"} onClose={onClose}
      footer={<><button className="bh-btn dark" onClick={onClose}>Vazgeç</button>
        <button className={`bh-btn ${direction === "IN" ? "green" : "red"}`} disabled={!k || !f.description.trim()} onClick={submit}>Kaydet</button></>}>
      <label className="form-label">Tarih</label>
      <input type="date" className="form-control mb-2" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} />
      <label className="form-label">Tutar ({account.currency})</label>
      <input className="form-control mb-2" placeholder="1.250,00" aria-label="Tutar" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} />
      <label className="form-label">Açıklama</label>
      <input className="form-control" aria-label="Açıklama" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
    </Modal>
  );
}

export default function AccountDetail() {
  const toast = useToast();
  const accs = useFetch(getAccounts), txs = useFetch(getTransactions), res = useFetch(getResults);
  const [accId, setAccId] = useState(null);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState(null);
  const acc = accs.data?.find((a) => a.id === (accId ?? accs.data?.[0]?.id));
  const reload = () => { txs.reload(); res.reload(); };
  const byTx = useMemo(() => { const m = {}; (res.data || []).forEach((x) => (m[x.transaction_id] ||= []).push(x)); return m; }, [res.data]);
  const rows = (txs.data || []).filter((t) => t.account_id === acc?.id && t.description.toLowerCase().includes(q.toLowerCase()));
  let bal = 0;
  const withBal = rows.map((t) => { bal += t.direction === "IN" ? t.amount_kurus : -t.amount_kurus; return { ...t, bal }; });
  const run = async () => {
    try { const r = await runMatching(); toast.ok(`Eşleştirme tamamlandı: ${r.processed} hareket işlendi.`); reload(); }
    catch (e) { toast.err(e.userMessage); }
  };
  const na = "Prototip kapsamı dışında";
  return (
    <>
      <div className="mb-2">
        <select className="form-select w-auto mb-2" aria-label="Hesap seç" value={acc?.id || ""} onChange={(e) => setAccId(+e.target.value)}>
          {(accs.data || []).map((a) => <option key={a.id} value={a.id}>{a.name} ({a.currency})</option>)}</select>
        <div className="bh-account"><div style={{ fontSize: 40 }}>{{ TRY: "₺", USD: "$", EUR: "€" }[acc?.currency] || ""}</div>
          <div><div style={{ fontSize: 26, fontWeight: 700 }}>{acc?.name || "…"}</div>
            <div>Bakiye : {fmtMoney(bal, acc?.currency)}</div></div></div>
      </div>
      <div className="d-flex flex-wrap gap-2">
        <button className="bh-btn info" disabled title={na}><Pencil size={13} />Güncelle</button>
        <button className="bh-btn green" disabled={!acc} onClick={() => setModal({ type: "money", dir: "IN" })}><ArrowDownToLine size={13} />Hesaba Para Girişi Yap</button>
        <button className="bh-btn red" disabled={!acc} onClick={() => setModal({ type: "money", dir: "OUT" })}><ArrowUpFromLine size={13} />Hesaptan Para Çıkışı Yap</button>
        <button className="bh-btn orange" disabled title={na}><ArrowRightLeft size={13} />Hesaplar Arası Transfer ▾</button>
        <button className="bh-btn teal" disabled title={na}><FileText size={13} />Dökümanlar</button>
        <button className="bh-btn match" onClick={run}><Wand2 size={13} />Otomatik Fatura Eşleştir</button>
      </div>
      <div className="bh-panel">
        <div className="bh-panel-h">Hesap Hareketleri</div>
        <div className="bh-panel-b">
          <div className="d-flex justify-content-end align-items-center gap-2 mb-2">
            <label>Bul:</label><input className="form-control w-50" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <div style={{ overflowX: "auto" }}>
            <table className="bh-table">
              <thead><tr><th>Tarih</th><th>İşlem</th><th>Kullanıcı</th><th>Hesap</th><th>Açıklama</th><th className="num">Borç</th>
                <th className="num">Alacak</th><th className="num">Bakiye</th><th>Eşleşen Fatura Numarası</th><th>Eşleşme Durumu</th><th>Eşleştirme Detayı</th></tr></thead>
              <tbody>
                {withBal.length === 0 && <tr><td colSpan={11} className="text-center text-muted">Eşleşen kayıt bulunamadı</td></tr>}
                {withBal.map((t) => {
                  const ms = byTx[t.id] || [], shown = ms.filter((x) => x.status === "APPROVED"), use = shown.length ? shown : ms.filter((x) => x.status === "SUGGESTED");
                  return (
                    <tr key={t.id}><td>{fmtDate(t.date)}</td><td>{t.direction === "IN" ? "Para Girişi" : "Para Çıkışı"}</td><td>Demo</td>
                      <td>{acc?.name}</td><td>{t.description}</td>
                      <td className="num">{t.direction === "OUT" ? fmtMoney(t.amount_kurus, t.currency) : ""}</td>
                      <td className="num">{t.direction === "IN" ? fmtMoney(t.amount_kurus, t.currency) : ""}</td>
                      <td className="num">{fmtMoney(t.bal, t.currency)}</td>
                      <td>{use.flatMap((x) => x.allocations.map((a) => a.invoice_no)).join(", ") || "–"}</td>
                      <td><StatusBadge status={t.status} /></td>
                      <td>{t.category === "PAYMENT" ? <button className="btn btn-link btn-sm p-0" onClick={() => setModal({ type: "detail", tx: t })}>Detay</button> : "–"}</td></tr>);
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      {modal?.type === "money" && acc && <MoneyModal account={acc} direction={modal.dir} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
      {modal?.type === "detail" && <TxDetailModal tx={modal.tx} accountName={acc?.name} matches={byTx[modal.tx.id] || []}
        onClose={() => setModal(null)} onChanged={reload} />}
    </>
  );
}
