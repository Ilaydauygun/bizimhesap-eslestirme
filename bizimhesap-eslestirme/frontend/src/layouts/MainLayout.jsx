import { Outlet } from "react-router-dom";
import { Menu, CalendarDays } from "lucide-react";
import Sidebar from "../components/Sidebar";
export default function MainLayout() {
  return (
    <div className="bh-wrap">
      <Sidebar />
      <div className="bh-main">
        <header className="bh-top">
          <Menu size={22} />
          <span className="d-flex align-items-center gap-3"><CalendarDays size={28} /> Demo Kullanıcı ▾</span>
        </header>
        <div className="bh-content"><Outlet /></div>
        <footer className="bh-footer">Prototip — gerçek Bizim Hesap sistemi ile bağlantısı yoktur. Sentetik veri.</footer>
      </div>
    </div>
  );
}
