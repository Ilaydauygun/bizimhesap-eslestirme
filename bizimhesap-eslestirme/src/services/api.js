import axios from "axios";
const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE || "/api" });
api.interceptors.response.use((r) => r, (e) => {
  let msg = e.response?.data?.detail;
  if (msg && typeof msg !== "string") msg = Array.isArray(msg) ? "Geçersiz istek." : JSON.stringify(msg);
  if (!msg) msg = e.response ? `Sunucu hatası (HTTP ${e.response.status}). Backend penceresindeki hata mesajına bakın.` : "Sunucuya ulaşılamadı. Backend çalışıyor mu?";
  e.userMessage = msg;      // her zaman metin: React'te nesne gösterilirse ekran çöker
  return Promise.reject(e);
});
const d = (p) => p.then((r) => r.data);
export const getAccounts = () => d(api.get("/bank-accounts"));
export const getTransactions = (params) => d(api.get("/bank-transactions", { params }));
export const createTransaction = (body) => d(api.post("/bank-transactions", body));
export const getInvoices = (params) => d(api.get("/invoices", { params }));
export const createInvoice = (body) => d(api.post("/invoices", body));
export const getStats = () => d(api.get("/dashboard/stats"));
export const runMatching = () => d(api.post("/reconciliation/run"));
export const getResults = () => d(api.get("/reconciliation/results"));
export const getCandidates = (id) => d(api.get(`/reconciliation/candidates/${id}`));
export const approveMatch = (match_id) => d(api.post("/reconciliation/approve", { match_id }));
export const rejectMatch = (match_id) => d(api.post("/reconciliation/reject", { match_id }));
export const undoMatch = (match_id) => d(api.post("/reconciliation/undo", { match_id }));
export const manualMatch = (transaction_id, allocations) => d(api.post("/reconciliation/manual", { transaction_id, allocations }));
export const getHistory = () => d(api.get("/reconciliation/history"));
export const getAuditLogs = () => d(api.get("/reconciliation/audit-logs"));
export const getSettings = () => d(api.get("/automation/settings"));
export const putSettings = (body) => d(api.put("/automation/settings", body));
export const getLogs = () => d(api.get("/automation/logs"));
export const uploadFile = async (path, file) => {
  const fd = new FormData(); fd.append("file", file);
  const r = await api.post(path, fd);
  const ok = r.data && typeof r.data === "object" && typeof r.data.imported === "number" && Array.isArray(r.data.errors);
  if (!ok) {   // beklenen biçimde değilse başarılı gibi gösterme; sunucunun gönderdiğini aynen göster
    const body = typeof r.data === "string" ? r.data : JSON.stringify(r.data);
    const err = new Error("Beklenmeyen cevap");
    err.userMessage = `Sunucudan beklenmeyen bir cevap geldi (HTTP ${r.status}, ${r.headers?.["content-type"] || "içerik türü yok"}). ` +
      `Cevabın başı: ${String(body ?? "").slice(0, 200) || "(boş)"}`;
    throw err;
  }
  return r.data;
};
export const exportUrl = (fmt) => `${api.defaults.baseURL}/reconciliation/export?format=${fmt}`;
export default api;
