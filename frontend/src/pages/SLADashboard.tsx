import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Badge from '../components/common/Badge';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatCard from '../components/common/StatCard';
import Table from '../components/common/Table';
import type { Column } from '../components/common/Table';
import { useApi } from '../hooks/useApi';
import { analyticsService } from '../services/analyticsService';
import type { SLA } from '../types';
import { formatDateTime, formatPercent } from '../utils/format';

export default function SLADashboard() {
  const metrics = useApi(() => analyticsService.slaMetrics(), []);
  const active = useApi(() => analyticsService.slaList({ status: 'ACTIVE' }), []);

  const columns: Column<SLA>[] = [
    {
      key: 'ticket',
      header: 'Ticket',
      render: (s) => (
        <Link className="text-brand-600 hover:underline" to={`/tickets/${s.ticket_id}`}>
          {s.ticket_id}
        </Link>
      ),
    },
    { key: 'policy', header: 'Policy', render: (s) => s.sla_policy },
    { key: 'priority', header: 'Priority', render: (s) => <Badge label={s.priority} /> },
    { key: 'target', header: 'Target', render: (s) => `${s.target_hours}h` },
    { key: 'due', header: 'Due', render: (s) => formatDateTime(s.due_at) },
    { key: 'status', header: 'Status', render: (s) => <Badge label={s.status} /> },
  ];

  const m = metrics.data;
  const chartData = Object.entries(m?.by_policy ?? {}).map(([name, v]) => ({ name, Met: v.met, Breached: v.breached }));

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">SLA Monitor</h1>
      {metrics.loading && <LoadingSpinner />}
      {metrics.error && <p className="text-sm text-red-600">{metrics.error}</p>}
      {m && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
          <StatCard label="Compliance" value={formatPercent(m.compliance_rate)} tone="good" />
          <StatCard label="Active" value={m.active} />
          <StatCard label="Warning" value={m.warning} tone="warn" />
          <StatCard label="Paused" value={m.paused} />
          <StatCard label="Breached" value={m.breached} tone="danger" />
        </div>
      )}
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Outcome by SLA policy">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="Met" fill="#059669" />
                <Bar dataKey="Breached" fill="#dc2626" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Active SLAs">
          {active.loading && <LoadingSpinner />}
          {active.data && <Table columns={columns} rows={active.data.items} rowKey={(s) => s.sla_id} />}
        </Card>
      </div>
    </div>
  );
}
