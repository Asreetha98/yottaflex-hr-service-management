import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/layout/Layout';
import ProtectedRoute from './routes/ProtectedRoute';
import { useAuth } from './hooks/useAuth';
import LoginPage from './pages/LoginPage';
import EmployeeDashboard from './pages/EmployeeDashboard';
import HRDashboard from './pages/HRDashboard';
import TicketManagement from './pages/TicketManagement';
import TicketDetail from './pages/TicketDetail';
import PolicyManagement from './pages/PolicyManagement';
import KnowledgeBase from './pages/KnowledgeBase';
import SLADashboard from './pages/SLADashboard';
import Analytics from './pages/Analytics';
import AdminPanel from './pages/AdminPanel';

/** Landing page depends on whether the user works tickets or only raises them. */
function Home() {
  const { hasPermission } = useAuth();
  return hasPermission('view_all_tickets') ? <HRDashboard /> : <EmployeeDashboard />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="tickets" element={<TicketManagement />} />
          <Route path="tickets/:ticketId" element={<TicketDetail />} />
          <Route path="knowledge" element={<KnowledgeBase />} />
          <Route element={<ProtectedRoute permissions={['manage_policies', 'manage_knowledge']} />}>
            <Route path="policies" element={<PolicyManagement />} />
          </Route>
          <Route element={<ProtectedRoute permissions={['view_all_tickets']} />}>
            <Route path="sla" element={<SLADashboard />} />
          </Route>
          <Route element={<ProtectedRoute permissions={['view_analytics']} />}>
            <Route path="analytics" element={<Analytics />} />
          </Route>
          <Route element={<ProtectedRoute permissions={['manage_users', 'view_audit_logs']} />}>
            <Route path="admin" element={<AdminPanel />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
