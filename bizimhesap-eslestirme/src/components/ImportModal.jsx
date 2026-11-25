import { useState } from "react";
import Modal from "./Modal";
import { uploadFile } from "../services/api";

export default function ImportModal({ title, path, hint, onClose, onDone }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const send = async () => {
    setBusy(true); setError(null);
    try { const r = await uploadFile(path, file);
      setResult(r); onDone?.(r); }
    catch (e) { setError(e.userMessage); }
    finally { setBusy(false); }
  };
  return (
    <Modal title={title} onClose={onClose}
      footer={<><button className="bh-btn dark" onClick={onClose}>Kapat</button>
        <button className="bh-btn green" disabled={!file || busy} onClick={send}>{busy ? "Yükleniyor…" : "Yükle"}</button></>}>
      <p className="text-muted small">{hint}</p>
      <input type="file" className="form-control mb-3" accept=".csv,.xlsx" aria-label="Dosya seç"
        onChange={(e) => { setFile(e.target.files[0] || null); setResult(null); setError(null); }} />
      {error && <div className="alert alert-danger">{String(error)}</div>}
      {result && (
        <div>
          <div className="alert alert-success mb-2">
            {result.imported} kayıt aktarıldı, {result.duplicates} mükerrer atlandı, {result.errors.length} satır hatalı.
          </div>
          {result.errors.length > 0 && (
            <table className="bh-table"><thead><tr><th>Satır</th><th>Hata</th></tr></thead>
              <tbody>{result.errors.map((e, i) => <tr key={i}><td>{String(e.row ?? "")}</td><td>{String(e.message ?? "")}</td></tr>)}</tbody></table>
          )}
        </div>
      )}
    </Modal>
  );
}
