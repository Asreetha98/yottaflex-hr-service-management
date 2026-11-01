import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Badge from '../components/common/Badge';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatCard from '../components/common/StatCard';
import Table from '../components/common/Table';
import type { Column } from '../components/common/Table';
import { useApi } from '../hooks/useApi';
import { analyticsService } from '../services/analyticsService';
import { ticketService } from '../services/ticketService';
import type { Ticket } from '../types';
import { formatDateTime, formatPercent } from '../utils/format';

export default function HRDashboard() {
  const overview = useApi(() => analyticsService.overview(), []);
  const tickets = useApi(() => analyticsService.tickets(), []);
  const queue = useApi(() => ticketService.list({ status: 'ESCALATED', limit: 10 }), []);

  const columns: Column<Ticket>[] = [
    {
      key: 'id',
      header: 'Ticket',
      render: (t) => (
        <Link className="text-brand-600 hover:underline" to={`/tickets/${t.ticket_id}`}>
          {t.ticket_id}
        </Link>
      ),
    },
    { key: 'subject', header: 'Subject', render: (t) => t.subject },
    { key: 'priority', header: 'Priority', render: (t) => <Badge label={t.priority} /> },
    { key: 'status', header: 'Status', render: (t) => <Badge label={t.status} /> },
    { key: 'created', header: 'Created', render: (t) => formatDateTime(t.created_at) },
  ];

  const categoryData = Object.entries(tickets.data?.by_category ?? {}).map(([name, count]) => ({ name, count }));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">HR Operations Dashboard</h1>

      {overview.loading && <LoadingSpinner />}
      {overview.error && <p className="text-sm text-red-600">{overview.error}</p>}
      {overview.data && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard label="Open tickets" value={overview.data.open_tickets} />
          <StatCard label="Awaiting clarification" value={overview.data.awaiting_clarification} tone="warn" />
          <StatCard label="Escalated" value={overview.data.escalated_tickets} tone="danger" />
          <StatCard label="Sensitive" value={overview.data.sensitive_tickets} tone="warn" />
          <StatCard label="Created (24h)" value={overview.data.created_last_24h} />
          <StatCard label="Resolved" value={overview.data.resolved_tickets} tone="good" />
          <StatCard label="SLA compliance" value={formatPercent(overview.data.sla_compliance_rate)} />
          <StatCard label="SLA breached" value={overview.data.sla_breached} tone="danger" />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Tickets by category">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={categoryData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="#2563eb" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Escalated queue">
          {queue.loading && <LoadingSpinner />}
          {queue.data && <Table columns={columns} rows={queue.data.items} rowKey={(t) => t.ticket_id} />}
        </Card>
      </div>
    </div>
  );
}
