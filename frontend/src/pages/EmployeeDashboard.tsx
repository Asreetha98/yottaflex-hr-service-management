import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Modal from '../components/common/Modal';
import StatCard from '../components/common/StatCard';
import Table from '../components/common/Table';
import type { Column } from '../components/common/Table';
import { useApi } from '../hooks/useApi';
import { errorMessage } from '../services/api';
import { analyticsService } from '../services/analyticsService';
import { ticketService } from '../services/ticketService';
import type { Ticket } from '../types';
import { formatDateTime } from '../utils/format';

export default function EmployeeDashboard() {
  const navigate = useNavigate();
  const summary = useApi(() => analyticsService.mySummary(), []);
  const tickets = useApi(() => ticketService.list({ mine: true, limit: 10 }), []);
  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const created = await ticketService.create({ subject, description, channel: 'PORTAL' });
      setOpen(false);
      setSubject('');
      setDescription('');
      navigate(`/tickets/${created.ticket_id}`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

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
    { key: 'category', header: 'Category', render: (t) => t.category_code ?? '—' },
    { key: 'status', header: 'Status', render: (t) => <Badge label={t.status} /> },
    { key: 'created', header: 'Created', render: (t) => formatDateTime(t.created_at) },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">My HR Requests</h1>
        <Button onClick={() => setOpen(true)}>New request</Button>
      </div>

      {summary.data && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard label="Total" value={summary.data.total_tickets} />
          <StatCard label="Open" value={summary.data.open_tickets} />
          <StatCard label="Awaiting your reply" value={summary.data.awaiting_clarification} tone="warn" />
          <StatCard label="Resolved" value={summary.data.resolved_tickets} tone="good" />
        </div>
      )}

      <Card title="Recent requests">
        {tickets.loading && <LoadingSpinner />}
        {tickets.error && <p className="text-sm text-red-600">{tickets.error}</p>}
        {tickets.data && (
          <Table columns={columns} rows={tickets.data.items} rowKey={(t) => t.ticket_id} />
        )}
      </Card>

      <Modal
        open={open}
        title="Submit an HR request"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="new-ticket-form" loading={submitting}>
              Submit
            </Button>
          </>
        }
      >
        <form id="new-ticket-form" onSubmit={submit} className="space-y-3">
          {error && <div className="rounded-md bg-red-50 p-2 text-sm text-red-700">{error}</div>}
          <label className="block text-sm">
            <span className="text-slate-700">Subject</span>
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              minLength={3}
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-700">Describe your request</span>
            <textarea
              className="mt-1 h-32 w-full rounded-md border border-slate-300 px-3 py-2"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              minLength={3}
              required
            />
          </label>
        </form>
      </Modal>
    </div>
  );
}
