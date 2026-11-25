import { Routes, Route, Navigate } from "react-router-dom";
import MainLayout from "./layouts/MainLayout";
import Reconciliation from "./pages/Reconciliation";
import AccountDetail from "./pages/AccountDetail";
import Invoices from "./pages/Invoices";
import Placeholder from "./pages/Placeholder";
import MatchHistory from "./pages/MatchHistory";
import AutomationSettings from "./pages/AutomationSettings";

export default function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route path="/" element={<Navigate to="/nakit/eslestirme" replace />} />
        <Route path="/musteriler" element={<Placeholder title="Müşteriler" />} />
        <Route path="/tedarikciler" element={<Placeholder title="Tedarikçiler" />} />
        <Route path="/satislar" element={<Invoices kind="SALE" />} />
        <Route path="/alislar" element={<Invoices kind="PURCH" />} />
        <Route path="/nakit/hesaplarim" element={<AccountDetail />} />
        <Route path="/nakit/eslestirme" element={<Reconciliation />} />
        <Route path="/nakit/gecmis" element={<MatchHistory />} />
        <Route path="/nakit/otomasyon" element={<AutomationSettings />} />
        <Route path="/raporlar" element={<Placeholder title="Raporlar" />} />
      </Route>
    </Routes>
  );
}
