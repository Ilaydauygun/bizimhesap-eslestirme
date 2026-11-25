import { STATUS } from "../services/format";
export default function StatusBadge({ status }) {
  const [cls, label] = STATUS[status] || ["out", status];
  return <span className={`st ${cls}`}>{label}</span>;
}
