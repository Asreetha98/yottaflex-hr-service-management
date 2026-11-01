import { useState } from 'react';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Table from '../components/common/Table';
import type { Column } from '../components/common/Table';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import { errorMessage } from '../services/api';
import { analyticsService } from '../services/analyticsService';
import type { AdminUser, AuditLogEntry, Page } from '../types';
import { formatDateTime } from '../utils/format';

export default function AdminPanel() {
  const { hasPermission } = useAuth();
  const canUsers = hasPermission('manage_users');
  const canAudit = hasPermission('view_audit_logs');
  const users = useApi<Page<AdminUser> | null>(() => (canUsers ? analyticsService.users() : Promise.resolve(null)), [canUsers]);
  const [eventType, setEventType] = useState('');
  const audit = useApi<Page<AuditLogEntry> | null>(
    () => (canAudit ? analyticsService.auditLogs({ event_type: eventType || undefined }) : Promise.resolve(null)),
    [canAudit, eventType],
  );
  const [error, setError] = useState<string | null>(null);

  const update = async (id: string, body: { is_active?: boolean; can_view_sensitive?: boolean }) => {
    setError(null);
    try {
      await analyticsService.updateUser(id, body);
      users.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  const userColumns: Column<AdminUser>[] = [
    { key: 'username', header: 'Username', render: (u) => u.username },
    { key: 'email', header: 'Email', render: (u) => u.email },
    {
      key: 'roles',
      header: 'Roles',
      render: (u) => (
        <div className="flex gap-1">
          {u.roles.map((r) => (
            <Badge key={r} label={r} tone="purple" />
          ))}
        </div>
      ),
    },
    { key: 'active', header: 'Active', render: (u) => <Badge label={u.is_active ? 'ACTIVE' : 'INACTIVE'} tone={u.is_active ? 'green' : 'gray'} /> },
    {
      key: 'sensitive',
      header: 'Sensitive access',
      render: (u) => <Badge label={u.can_view_sensitive ? 'YES' : 'NO'} tone={u.can_view_sensitive ? 'amber' : 'gray'} />,
    },
    {
      key: 'actions',
      header: '',
      render: (u) => (
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => void update(u.user_id, { is_active: !u.is_active })}>
            {u.is_active ? 'Deactivate' : 'Activate'}
          </Button>
          <Button variant="secondary" onClick={() => void update(u.user_id, { can_view_sensitive: !u.can_view_sensitive })}>
            Toggle sensitive
          </Button>
        </div>
      ),
    },
  ];

  const auditColumns: Column<AuditLogEntry>[] = [
    { key: 'id', header: 'Event', render: (a) => <span className="font-mono text-xs">{a.event_id}</span> },
    { key: 'type', header: 'Type', render: (a) => a.event_type },
    { key: 'entity', header: 'Entity', render: (a) => `${a.entity_type} ${a.entity_id ?? ''}` },
    { key: 'actor', header: 'Actor', render: (a) => a.actor_user_id ?? 'system' },
    { key: 'at', header: 'At', render: (a) => formatDateTime(a.created_at) },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Administration</h1>
      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {canUsers && (
        <Card title="Users">
          {users.loading && <LoadingSpinner />}
          {users.error && <p className="text-sm text-red-600">{users.error}</p>}
          {users.data && <Table columns={userColumns} rows={users.data.items} rowKey={(u) => u.user_id} />}
        </Card>
      )}

      {canAudit && (
        <Card
          title="Audit log (append-only)"
          actions={
            <input
              className="rounded-md border border-slate-300 px-2 py-1 text-sm"
              placeholder="Filter by event type"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
            />
          }
        >
          {audit.loading && <LoadingSpinner />}
          {audit.error && <p className="text-sm text-red-600">{audit.error}</p>}
          {audit.data && <Table columns={auditColumns} rows={audit.data.items} rowKey={(a) => a.event_id} />}
        </Card>
      )}
    </div>
  );
}
