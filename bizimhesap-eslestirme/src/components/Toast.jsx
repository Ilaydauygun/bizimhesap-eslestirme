import { createContext, useContext, useState, useCallback } from "react";
const Ctx = createContext({ ok: () => {}, err: () => {} });
export const useToast = () => useContext(Ctx);
export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((kind, text) => {
    const id = Math.random();
    setItems((x) => [...x, { id, kind, text }]);
    setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), kind === "err" ? 7000 : 4000);
  }, []);
  const api = { ok: (t) => push("ok", t), err: (t) => push("err", t) };
  return (
    <Ctx.Provider value={api}>
      {children}
      <div style={{ position: "fixed", top: 70, right: 20, zIndex: 3000, width: 360 }} role="status">
        {items.map((i) => (
          <div key={i.id} className="bh-alert" style={{ background: i.kind === "ok" ? "#dff0d8" : "#f2dede",
            color: i.kind === "ok" ? "#3c763d" : "#a94442", padding: "12px 16px", marginBottom: 8 }}>{i.text}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
