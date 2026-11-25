export const fmtMoney = (kurus, cur = "TRY") =>
  (kurus / 100).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) +
  " " + ({ TRY: "₺", USD: "$", EUR: "€" }[cur] || cur);
export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("tr-TR") : "");
export const fmtDateTime = (iso) => (iso ? new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toLocaleString("tr-TR") : "–");
export const STATUS = {
  MATCHED: ["matched", "Eşleşti"], PENDING: ["pending", "Onay Bekliyor"], UNMATCHED: ["unmatched", "Eşleşmedi"],
  PARTIAL: ["partial", "Kısmi Eşleşme"], OUT_OF_SCOPE: ["out", "Kapsam Dışı"],
};
export const MATCH_STATUS = { APPROVED: "Onaylandı", REJECTED: "Reddedildi", UNDONE: "Geri Alındı", SUGGESTED: "Önerildi" };
export const KIND = { FULL: "Tam ödeme", PARTIAL: "Kısmi ödeme", OVERPAY: "Fazla ödeme", BULK: "Toplu ödeme" };

/** "1.234,56" -> kuruş (tam sayı). float kullanılmaz. Geçersizse null. */
export function parseTRY(text) {
  let t = String(text ?? "").trim().replace(/\s/g, "");
  if (!t) return null;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(t);
  if (!m) return null;
  return parseInt(m[1], 10) * 100 + parseInt((m[2] || "0").padEnd(2, "0"), 10);
}
export const kurusToInput = (k) => `${Math.floor(k / 100)},${String(k % 100).padStart(2, "0")}`;
export const kurusToDecimalStr = (k) => `${Math.floor(k / 100)}.${String(k % 100).padStart(2, "0")}`;
