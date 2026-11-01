import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import LoadingSpinner from '../components/common/LoadingSpinner';

interface Props {
  /** Allowed if the user holds ANY of these permissions. Omit to allow any signed-in user. */
  permissions?: string[];
}

export default function ProtectedRoute({ permissions }: Props) {
  const { user, loading, hasPermission } = useAuth();
  const location = useLocation();

  if (loading) return <LoadingSpinner label="Checking session" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (permissions && !permissions.some(hasPermission)) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-amber-900">
        <h2 className="text-lg font-semibold">Access denied</h2>
        <p className="mt-1 text-sm">Your role does not include access to this page.</p>
      </div>
    );
  }
  return <Outlet />;
}
