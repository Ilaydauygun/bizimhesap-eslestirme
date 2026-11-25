import { X } from "lucide-react";
export default function Modal({ title, onClose, children, footer, wide }) {
  return (
    <div role="dialog" aria-label={title} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 2000,
      overflowY: "auto", padding: "40px 16px" }} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div style={{ background: "#fff", maxWidth: wide ? 1100 : 560, margin: "0 auto", boxShadow: "0 5px 25px rgba(0,0,0,.4)" }}>
        <div className="bh-panel-h d-flex justify-content-between align-items-center" style={{ padding: "14px 20px" }}>
          <span>{title}</span>
          <button className="btn btn-sm text-white" aria-label="Kapat" onClick={onClose}><X size={18} /></button>
        </div>
        <div style={{ padding: 20 }}>{children}</div>
        {footer && <div className="d-flex justify-content-end gap-2" style={{ padding: "0 20px 20px" }}>{footer}</div>}
      </div>
    </div>
  );
}
