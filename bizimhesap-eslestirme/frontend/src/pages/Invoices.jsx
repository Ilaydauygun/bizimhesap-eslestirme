import { useState } from "react";
import { Plus, Upload } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { getInvoices, createInvoice } from "../services/api";
import { fmtMoney, fmtDate, parseTRY, kurusToDecimalStr } from "../services/format";
import Modal from "../components/Modal";
import ImportModal from "../components/ImportModal";
import { useToast } from "../components/Toast";

const DOCS = ["Sipariş", "İrsaliye", "Faturalaşmış", "E-Faturalaşmış", "E-Faturalaşmamış"];
const DOCS_PURCH = ["Sipariş", "İrsaliyeleşmiş", "Faturalaşmış"];

function NewInvoice({ kind, onClose, onDone }) {
  const toast = useToast();
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({ invoice_no: "", party_name: "", issue_date: today, due_date: today, total: "", currency: "TRY", doc_type: "Faturalaşmış" });
  const k = parseTRY(f.total);
  const submit = async () => {
    try { await createInvoice({ ...f, kind, total: kurusToDecimalStr(k) }); toast.ok("Fatura oluşturuldu."); onDone(); }
    catch (e) { toast.err(e.userMessage); }
  };
  const set = (n) => (e) => setF({ ...f, [n]: e.target.value });
  return (
    <Modal title={kind === "SALE" ? "Yeni Satış Faturası" : "Yeni Alış Faturası"} onClose={onClose}
      footer={<><button className="bh-btn dark" onClick={onClose}>Vazgeç</button>
        <button className="bh-btn green" disabled={!k || !f.invoice_no || !f.party_name} onClick={submit}>Kaydet</button></>}>
      <input className="form-control mb-2" placeholder="Fatura No" aria-label="Fatura No" value={f.invoice_no} onChange={set("invoice_no")} />
      <input className="form-control mb-2" placeholder={kind === "SALE" ? "Müşteri ünvanı" : "Tedarikçi ünvanı"} aria-label="Cari ünvan" value={f.party_name} onChange={set("party_name")} />
      <div className="row g-2 mb-2"><div className="col"><input type="date" className="form-control" value={f.issue_date} onChange={set("issue_date")} /></div>
        <div className="col"><input type="date" className="form-control" value={f.due_date} onChange={set("due_date")} /></div></div>
      <div className="row g-2"><div className="col"><input className="form-control" placeholder="Tutar 1.250,00" aria-label="Tutar" value={f.total} onChange={set("total")} /></div>
        <div className="col-3"><select className="form-select" value={f.currency} onChange={set("currency")}><option>TRY</option><option>USD</option><option>EUR</option></select></div>
        <div className="col-4"><select className="form-select" value={f.doc_type} onChange={set("doc_type")}>
          {(kind === "SALE" ? DOCS : DOCS_PURCH).map((d) => <option key={d}>{d}</option>)}</select></div></div>
    </Modal>
  );
}

export default function Invoices({ kind }) {
  const [f, setF] = useState({ q: "", status: "", doc: "" });
  const [modal, setModal] = useState(null);
  const { data, error, reload } = useFetch(() => getInvoices({ kind }), [kind]);
  const rows = (data || []).filter((i) => (!f.q || i.invoice_no.toLowerCase().includes(f.q.toLowerCase()))
    && (!f.status || i.status === f.status) && (!f.doc || i.doc_type === f.doc));
  const sum = (key) => rows.filter((i) => i.currency === "TRY" && i.status !== "İptal Edildi").reduce((a, i) => a + i[key], 0);
  return (
    <>
      <div className="d-flex gap-2 mb-2">
        <button className="bh-btn red" onClick={() => setModal("new")}><Plus size={13} />{kind === "SALE" ? "Yeni Satış Faturası" : "Yeni Alış Faturası"}</button>
        <button className="bh-btn info" onClick={() => setModal("up")}><Upload size={13} />Fatura Yükle</button>
      </div>
      {error && <div className="bh-alert">{error}</div>}
      <div className="bh-panel">
        <div className="bh-panel-h">{kind === "SALE" ? "Satış Faturaları" : "Alış Faturaları"}</div>
        <div className="bh-panel-b">
          <div className="d-flex flex-wrap gap-2 mb-2">
            <select className="form-select w-auto" aria-label="Belge tipi" value={f.doc} onChange={(e) => setF({ ...f, doc: e.target.value })}>
              <option value="">Tüm Belge Tipleri</option>{(kind === "SALE" ? DOCS : DOCS_PURCH).map((d) => <option key={d}>{d}</option>)}</select>
            <select className="form-select w-auto" aria-label="Ödeme durumu" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
              <option value="">Tüm Ödeme Durumları</option><option>Ödenmedi</option><option>Kısmen Ödendi</option><option>Ödendi</option><option>İptal Edildi</option></select>
            <input className="form-control w-auto" placeholder="Fatura no ara…" aria-label="Fatura no ara" value={f.q} onChange={(e) => setF({ ...f, q: e.target.value })} />
          </div>
          <div style={{ overflowX: "auto" }}>
            <table className="bh-table">
              <thead><tr><th>Fatura No</th><th>Belge Tipi</th><th>{kind === "SALE" ? "Müşteri" : "Tedarikçi"}</th><th>Fatura Tarihi</th><th>Vade</th>
                <th className="num">Toplam</th><th className="num">Ödenen</th><th className="num">Kalan Borç</th><th>Para Birimi</th><th>Durum</th></tr></thead>
              <tbody>
                {rows.map((i) => (
                  <tr key={i.id}><td>{i.invoice_no}</td><td>{i.doc_type}</td><td>{i.party}</td><td>{fmtDate(i.issue_date)}</td><td>{fmtDate(i.due_date)}</td>
                    <td className="num">{fmtMoney(i.total_kurus, i.currency)}</td><td className="num">{fmtMoney(i.paid_kurus, i.currency)}</td>
                    <td className="num">{fmtMoney(i.remaining_kurus, i.currency)}</td><td>{i.currency}</td><td>{i.status}</td></tr>))}
                {rows.length === 0 && <tr><td colSpan={10} className="text-center text-muted">Kayıt bulunamadı</td></tr>}
              </tbody>
              <tfoot><tr><th colSpan={5} className="text-end">TL toplamı (iptaller hariç):</th><th className="num">{fmtMoney(sum("total_kurus"))}</th>
                <th className="num">{fmtMoney(sum("paid_kurus"))}</th><th className="num">{fmtMoney(sum("remaining_kurus"))}</th><th colSpan={2}></th></tr></tfoot>
            </table>
          </div>
        </div>
      </div>
      {modal === "new" && <NewInvoice kind={kind} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
      {modal === "up" && <ImportModal title="Fatura Yükle" path="/invoices/import" onClose={() => setModal(null)} onDone={reload}
        hint="Sütunlar: fatura_no; tur (Satış/Alış); cari_unvan; fatura_tarihi; vade_tarihi; tutar; para_birimi; odenen ve belge_tipi isteğe bağlı." />}
    </>
  );
}
