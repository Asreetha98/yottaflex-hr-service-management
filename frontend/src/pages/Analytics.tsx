import { Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from 'recharts';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import StatCard from '../components/common/StatCard';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import { analyticsService } from '../services/analyticsService';
import type { EvaluationMetrics } from '../types';
import { formatNumber, formatPercent } from '../utils/format';

const COLORS = ['#2563eb', '#059669', '#d97706', '#7c3aed', '#dc2626', '#0891b2', '#64748b'];

export default function Analytics() {
  const { hasPermission } = useAuth();
  const tickets = useApi(() => analyticsService.tickets(), []);
  const performance = useApi(() => analyticsService.performance(), []);
  const canEvaluate = hasPermission('manage_config');
  const evaluation = useApi<EvaluationMetrics | null>(
    () => (canEvaluate ? analyticsService.evaluation() : Promise.resolve(null)),
    [canEvaluate],
  );

  const status = Object.entries(tickets.data?.by_status ?? {}).map(([name, value]) => ({ name, value }));
  const p = performance.data;
  const ev = evaluation.data;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Analytics</h1>

      {performance.loading && <LoadingSpinner />}
      {p && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard label="Avg resolution (business h)" value={formatNumber(p.avg_resolution_business_hours)} />
          <StatCard label="Avg first response (business h)" value={formatNumber(p.avg_first_response_business_hours)} />
          <StatCard label="SLA compliance" value={formatPercent(p.sla_compliance_rate)} tone="good" />
          <StatCard label="Reopen rate" value={formatPercent(p.reopen_rate)} tone="warn" />
          <StatCard label="Escalation rate" value={formatPercent(p.escalation_rate)} />
          <StatCard label="Avg satisfaction" value={formatNumber(p.avg_satisfaction, 2)} />
          <StatCard label="Resolved" value={p.resolved_count} />
          <StatCard label="Ambiguous tickets" value={tickets.data?.ambiguous ?? 0} tone="warn" />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Daily ticket volume">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tickets.data?.daily_volume ?? []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#2563eb" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Tickets by status">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={status} dataKey="value" nameKey="name" outerRadius={90} label>
                  {status.map((entry, i) => (
                    <Cell key={entry.name} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {canEvaluate && (
        <Card title="Classification evaluation (vs. ground truth)">
          {ev && !ev.available && <p className="text-sm text-slate-500">{ev.reason ?? 'Ground truth not available.'}</p>}
          {ev && ev.available && (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard label="Evaluated" value={ev.evaluated} />
              <StatCard label="Category accuracy" value={formatPercent(ev.category_accuracy)} />
              <StatCard label="Sensitive precision" value={formatPercent(ev.sensitive_precision)} />
              <StatCard label="Sensitive recall" value={formatPercent(ev.sensitive_recall)} />
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
