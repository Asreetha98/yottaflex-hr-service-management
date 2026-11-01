import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import Badge from '../common/Badge';
import Button from '../common/Button';

export default function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
      <div className="text-sm text-slate-500">Enterprise HR Service Management &amp; Policy Resolution</div>
      <div className="flex items-center gap-3">
        <div className="text-right">
          <div className="text-sm font-medium text-slate-800">{user?.username}</div>
          <div className="flex justify-end gap-1">
            {user?.roles.map((r) => (
              <Badge key={r} label={r} tone="purple" />
            ))}
          </div>
        </div>
        <Button variant="secondary" onClick={handleLogout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}
