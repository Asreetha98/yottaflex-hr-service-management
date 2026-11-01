import { NavLink } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

interface NavItem {
  to: string;
  label: string;
  /** Visible if the user holds ANY of these permissions; omitted = everyone. */
  anyOf?: string[];
}

const items: NavItem[] = [
  { to: '/', label: 'Dashboard' },
  { to: '/tickets', label: 'Tickets' },
  { to: '/knowledge', label: 'Knowledge Base' },
  { to: '/policies', label: 'Policies', anyOf: ['manage_policies', 'manage_knowledge'] },
  { to: '/sla', label: 'SLA Monitor', anyOf: ['view_all_tickets'] },
  { to: '/analytics', label: 'Analytics', anyOf: ['view_analytics'] },
  { to: '/admin', label: 'Administration', anyOf: ['manage_users', 'view_audit_logs'] },
];

export default function Sidebar() {
  const { hasPermission } = useAuth();
  const visible = items.filter((i) => !i.anyOf || i.anyOf.some(hasPermission));

  return (
    <aside className="hidden w-60 shrink-0 flex-col bg-slate-900 text-slate-100 md:flex">
      <div className="px-5 py-5">
        <div className="text-lg font-semibold">YottaFlex AI</div>
        <div className="text-xs text-slate-400">HR Service Management</div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {visible.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `block rounded-md px-3 py-2 text-sm ${
                isActive ? 'bg-brand-600 text-white' : 'text-slate-300 hover:bg-slate-800'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
