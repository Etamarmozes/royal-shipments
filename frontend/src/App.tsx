import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./auth/ProtectedRoute";
import Login from "./pages/Login";
import ChangePassword from "./pages/ChangePassword";
import Users from "./pages/Users";
import Dashboard from "./pages/Dashboard";
import Shipments from "./pages/Shipments";
import ShipmentProfile from "./pages/ShipmentProfile";
import Containers from "./pages/Containers";
import ContainersInTransit from "./pages/ContainersInTransit";
import ContainerProfile from "./pages/ContainerProfile";
import Categories from "./pages/Categories";
import Documents from "./pages/Documents";
import Receiving from "./pages/Receiving";
import SupplierHelp from "./pages/SupplierHelp";
import Forecast from "./pages/Forecast";
import DailyForecast from "./pages/DailyForecast";
import EmailUpdates from "./pages/EmailUpdates";
import PendingShipments from "./pages/PendingShipments";
import ExtraWork from "./pages/ExtraWork";
import Alerts from "./pages/Alerts";
import History from "./pages/History";
import DataReview from "./pages/DataReview";
import ImportExcel from "./pages/ImportExcel";
import ImportBatches from "./pages/ImportBatches";
import DocumentAssignmentReview from "./pages/DocumentAssignmentReview";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />
      <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="shipments" element={<Shipments />} />
        <Route path="shipments/:id" element={<ShipmentProfile />} />
        <Route path="containers" element={<Containers />} />
        <Route path="containers/:id" element={<ContainerProfile />} />
        <Route path="containers-in-transit" element={<ContainersInTransit />} />
        <Route path="categories" element={<Categories />} />
        <Route path="documents" element={<Documents />} />
        <Route path="receiving" element={<Receiving />} />
        <Route path="help/supplier" element={<SupplierHelp />} />
        <Route path="users" element={
          <ProtectedRoute requireRole={["admin"]}><Users /></ProtectedRoute>
        } />
        <Route path="forecast" element={<Forecast />} />
        <Route path="forecast-daily" element={<DailyForecast />} />
        <Route path="email-updates" element={<EmailUpdates />} />
        <Route path="pending-shipments" element={<PendingShipments />} />
        <Route path="extra-work" element={<ExtraWork />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="history" element={<History />} />
        <Route path="data-review" element={
          <ProtectedRoute requireRole={["admin", "import_manager"]}><DataReview /></ProtectedRoute>
        } />
        <Route path="document-review" element={
          <ProtectedRoute requireRole={["admin", "import_manager"]}><DocumentAssignmentReview /></ProtectedRoute>
        } />
        <Route path="import-excel" element={
          <ProtectedRoute requireRole={["admin", "import_manager"]}><ImportExcel /></ProtectedRoute>
        } />
        <Route path="import-batches" element={
          <ProtectedRoute requireRole={["admin", "import_manager"]}><ImportBatches /></ProtectedRoute>
        } />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  );
}
