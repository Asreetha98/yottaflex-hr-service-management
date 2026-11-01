import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Table from '../components/common/Table';
import type { Column } from '../components/common/Table';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import { ticketService } from '../services/ticketService';
import type { Ticket } from '../types';
import { formatDateTime } from '../utils/format';

const STATUSES = [
  'NEW',
  'CLASSIFIED',
  'AWAITING_CLARIFICATION',
  'ASSIGNED',
  'IN_PROGRESS',
  'ESCALATED',
  'RESOLVED',
  'CLOSED',
  'REOPENED',
  'CANCELLED',
];
const CATEGORIES = ['PAYROLL', 'LEAVE', 'BENEFITS', 'ONBOARDING'];
const PAGE_SIZE = 25;

export default function TicketManagement() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const canSeeAll = hasPermission('view_all_tickets') || hasPermission('view_team_tickets');
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState('');
  const [search, setSearch] = useState('');
  const [mine, setMine] = useState(!canSeeAll);
  const [page, setPage] = useState(0);

  const { data, loading, error } = useApi(
    () =>
      ticketService.list({
        status: status || undefined,
        category: category || undefined,
        priority: priority || undefined,
        search: search || undefined,
        mine,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    [status, category, priority, search, mine, page],
  );

  const columns: Column<Ticket>[] = [
    { key: 'id', header: 'Ticket', render: (t) => <span className="font-mono text-xs">{t.ticket_id}</span> },
    {
      key: 'subject',
      header: 'Subject',
      render: (t) => (
        <span>
          {t.subject} {t.is_sensitive && <Badge label="SENSITIVE" tone="red" />}
        </span>
      ),
    },
    { key: 'category', header: 'Category', render: (t) => t.category_code ?? '—' },
    { key: 'priority', header: 'Priority', render: (t) => <Badge label={t.priority} /> },
    { key: 'status', header: 'Status', render: (t) => <Badge label={t.status} /> },
    { key: 'created', header: 'Created', render: (t) => formatDateTime(t.created_at) },
  ];

  const total = data?.total ?? 0;
  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
  const reset = (fn: () => void) => {
    fn();
    setPage(0);
  };

  const selectClass = 'rounded-md border border-slate-300 px-2 py-1.5 text-sm';

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-slate-900">Tickets</h1>
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <input
            className={`${selectClass} w-64`}
            placeholder="Search subject or description"
            value={search}
            onChange={(e) => reset(() => setSearch(e.target.value))}
          />
          <select className={selectClass} value={status} onChange={(e) => reset(() => setStatus(e.target.value))}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
          <select className={selectClass} value={category} onChange={(e) => reset(() => setCategory(e.target.value))}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select className={selectClass} value={priority} onChange={(e) => reset(() => setPriority(e.target.value))}>
            <option value="">All priorities</option>
            {['P1', 'P2', 'P3'].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          {canSeeAll && (
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={mine} onChange={(e) => reset(() => setMine(e.target.checked))} />
              Only my tickets
            </label>
          )}
        </div>
      </Card>

      <Card>
        {loading && <LoadingSpinner />}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {data && (
          <>
            <Table
              columns={columns}
              rows={data.items}
              rowKey={(t) => t.ticket_id}
              onRowClick={(t) => navigate(`/tickets/${t.ticket_id}`)}
            />
            <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
              <span>
                {total} ticket{total === 1 ? '' : 's'}
              </span>
              <div className="flex items-center gap-2">
                <Button variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>
                  Previous
                </Button>
                <span>
                  Page {page + 1} of {lastPage + 1}
                </span>
                <Button variant="secondary" disabled={page >= lastPage} onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
