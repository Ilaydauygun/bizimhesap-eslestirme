import { NavLink, useLocation } from "react-router-dom";
import { Home, Users, Factory, ShoppingCart, Truck, Landmark, BarChart3, Plus, Minus } from "lucide-react";
const item = (to, Icon, label) => (
  <NavLink to={to} end className={({ isActive }) => (isActive ? "active" : "")}><Icon size={18} />{label}</NavLink>
);
export default function Sidebar() {
  const { pathname } = useLocation();
  const cashOpen = pathname.startsWith("/nakit");
  return (
    <aside className="bh-sidebar">
      <div className="bh-logo">bizim<br />hesap</div>
      <nav className="bh-nav">
        {item("/", Home, "ANA SAYFA")}
        {item("/musteriler", Users, "Müşteriler")}
        {item("/tedarikciler", Factory, "Tedarikçiler")}
        {item("/satislar", ShoppingCart, "Satışlar")}
        {item("/alislar", Truck, "Alışlar")}
        <div className={`bh-item ${cashOpen ? "open" : ""}`}><Landmark size={18} />Nakit Yönetimi
          <span className="plus">{cashOpen ? <Minus size={14} /> : <Plus size={14} />}</span></div>
        {cashOpen && (
          <div className="bh-sub">
            <NavLink to="/nakit/hesaplarim">Hesaplarım</NavLink>
            <NavLink to="/nakit/eslestirme">Banka-Fatura Eşleştirme</NavLink>
            <NavLink to="/nakit/gecmis">Eşleşme Geçmişi</NavLink>
            <NavLink to="/nakit/otomasyon">Otomasyon Ayarları</NavLink>
            <a className="disabled">Çalışanlar</a><a className="disabled">Masraflar</a>
            <a className="disabled">Gelen E-Faturalar</a><a className="disabled">Krediler</a>
          </div>
        )}
        {item("/raporlar", BarChart3, "Raporlar")}
      </nav>
    </aside>
  );
}
