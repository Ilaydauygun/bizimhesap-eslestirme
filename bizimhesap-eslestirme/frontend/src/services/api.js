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
export const uploadFile = (path, file) => {
  const fd = new FormData(); fd.append("file", file);
  return d(api.post(path, fd));
};
export const exportUrl = (fmt) => `${api.defaults.baseURL}/reconciliation/export?format=${fmt}`;
export default api;
