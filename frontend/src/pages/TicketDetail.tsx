import { useState } from 'react';
import type { FormEvent } from 'react';
import { useParams } from 'react-router-dom';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Modal from '../components/common/Modal';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../hooks/useAuth';
import { errorMessage } from '../services/api';
import { ticketService } from '../services/ticketService';
import type { KnowledgeHit, SLA, TicketDetail as TicketDetailType } from '../types';
import { formatDateTime } from '../utils/format';

type Dialog = 'escalate' | 'resolve' | 'reopen' | null;

const RESOLUTION_TYPES = ['POLICY_ANSWER', 'ACTION_COMPLETED', 'REFERRED', 'NO_ACTION_REQUIRED', 'DUPLICATE'];

export default function TicketDetail() {
  const { ticketId = '' } = useParams<{ ticketId: string }>();
  const { hasPermission } = useAuth();
  const ticket = useApi(() => ticketService.get(ticketId), [ticketId]);
  const sla = useApi<SLA | null>(() => ticketService.sla(ticketId).catch(() => null), [ticketId]);
  const suggestions = useApi<KnowledgeHit[]>(
    () => (hasPermission('manage_tickets') ? ticketService.suggestions(ticketId) : Promise.resolve([])),
    [ticketId],
  );

  const [reply, setReply] = useState('');
  const [internal, setInternal] = useState(false);
  const [dialog, setDialog] = useState<Dialog>(null);
  const [reason, setReason] = useState('');
  const [resolutionType, setResolutionType] = useState(RESOLUTION_TYPES[0]);
  const [summary, setSummary] = useState('');
  const [resolutionText, setResolutionText] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const t: TicketDetailType | null = ticket.data;
  const canWork = hasPermission('manage_tickets');
  const canResolve = hasPermission('resolve_tickets');
  const canEscalate = hasPermission('escalate_ticket');

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setActionError(null);
    try {
      await action();
      setDialog(null);
      setReason('');
      setSummary('');
      setResolutionText('');
      ticket.reload();
      sla.reload();
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const sendReply = (e: FormEvent) => {
    e.preventDefault();
    if (!reply.trim()) return;
    void run(async () => {
      await ticketService.addMessage(ticketId, reply, internal);
      setReply('');
    });
  };

  if (ticket.loading && !t) return <LoadingSpinner />;
  if (ticket.error) return <p className="text-sm text-red-600">{ticket.error}</p>;
  if (!t) return null;

  const closed = ['CLOSED', 'CANCELLED'].includes(t.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="font-mono text-xs text-slate-500">{t.ticket_id}</div>
          <h1 className="text-xl font-semibold text-slate-900">{t.subject}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge label={t.status} />
            <Badge label={t.priority} />
            {t.category_code && <Badge label={t.category_code} tone="blue" />}
            {t.is_sensitive && <Badge label="SENSITIVE" tone="red" />}
            {t.is_ambiguous && <Badge label="AMBIGUOUS" tone="amber" />}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canWork && ['CLASSIFIED', 'AWAITING_CLARIFICATION', 'NEW', 'REOPENED', 'ESCALATED'].includes(t.status) && (
            <Button variant="secondary" disabled={busy} onClick={() => void run(() => ticketService.assign(t.ticket_id))}>
              Auto-assign
            </Button>
          )}
          {canWork && ['ASSIGNED', 'REOPENED', 'ESCALATED'].includes(t.status) && (
            <Button disabled={busy} onClick={() => void run(() => ticketService.start(t.ticket_id))}>
              Start work
            </Button>
          )}
          {canEscalate && !closed && t.status !== 'ESCALATED' && (
            <Button variant="secondary" onClick={() => setDialog('escalate')}>
              Escalate
            </Button>
          )}
          {canResolve && t.status === 'IN_PROGRESS' && <Button onClick={() => setDialog('resolve')}>Resolve</Button>}
          {canResolve && t.status === 'RESOLVED' && (
            <Button disabled={busy} onClick={() => void run(() => ticketService.close(t.ticket_id))}>
              Close
            </Button>
          )}
          {t.status === 'RESOLVED' && (
            <Button variant="secondary" onClick={() => setDialog('reopen')}>
              Reopen
            </Button>
          )}
          {!closed && (
            <Button variant="danger" disabled={busy} onClick={() => void run(() => ticketService.cancel(t.ticket_id))}>
              Cancel
            </Button>
          )}
        </div>
      </div>

      {actionError && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{actionError}</div>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card title="Description">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{t.description}</p>
          </Card>

          <Card title="Conversation">
            <ul className="space-y-3">
              {t.messages.map((m) => (
                <li
                  key={m.message_id}
                  className={`rounded-md border p-3 text-sm ${
                    m.is_internal ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white'
                  }`}
                >
                  <div className="mb-1 flex justify-between text-xs text-slate-500">
                    <span>
                      {m.sender_type} {m.is_internal && '· internal note'}
                    </span>
                    <span>{formatDateTime(m.created_at)}</span>
                  </div>
                  <p className="whitespace-pre-wrap text-slate-800">{m.body}</p>
                </li>
              ))}
              {t.messages.length === 0 && <li className="text-sm text-slate-500">No messages yet.</li>}
            </ul>
            {!closed && (
              <form onSubmit={sendReply} className="mt-4 space-y-2">
                <textarea
                  className="h-24 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="Write a message"
                  value={reply}
                  onChange={(e) => setReply(e.target.value)}
                />
                <div className="flex items-center justify-between">
                  {canWork ? (
                    <label className="flex items-center gap-2 text-sm text-slate-600">
                      <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} />
                      Internal note
                    </label>
                  ) : (
                    <span />
                  )}
                  <Button type="submit" loading={busy}>
                    Send
                  </Button>
                </div>
              </form>
            )}
          </Card>

          {t.resolutions.length > 0 && (
            <Card title="Resolution">
              {t.resolutions.map((r) => (
                <div key={r.resolution_id} className="text-sm">
                  <div className="font-medium">{r.summary}</div>
                  <p className="mt-1 whitespace-pre-wrap text-slate-700">{r.resolution_text}</p>
                  <div className="mt-1 text-xs text-slate-500">
                    {r.resolution_type} · {formatDateTime(r.resolved_at)}
                    {r.policy_version_id && ` · ${r.policy_version_id}`}
                  </div>
                </div>
              ))}
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card title="SLA">
            {sla.data ? (
              <dl className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Status</dt>
                  <dd>
                    <Badge label={sla.data.status} />
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Target</dt>
                  <dd>{sla.data.target_hours}h ({sla.data.sla_policy})</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Due</dt>
                  <dd>{formatDateTime(sla.data.due_at)}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-slate-500">No SLA record.</p>
            )}
          </Card>

          <Card title="Classification">
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between">
                <dt className="text-slate-500">Confidence</dt>
                <dd>
                  {t.classification_confidence === null ? 'n/a' : `${(t.classification_confidence * 100).toFixed(0)}%`}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Access level</dt>
                <dd>{t.access_level}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Assigned team</dt>
                <dd>{t.assigned_team_id ?? '—'}</dd>
              </div>
            </dl>
          </Card>

          {canWork && (
            <Card title="Policy-backed suggestions">
              {suggestions.loading && <LoadingSpinner />}
              <ul className="space-y-3 text-sm">
                {(suggestions.data ?? []).map((s) => (
                  <li key={s.article_id}>
                    <div className="font-medium">{s.title}</div>
                    <p className="text-slate-600">{s.answer_snippet}</p>
                    {s.citation && (
                      <div className="text-xs text-slate-500">
                        {s.citation.policy_title} v{s.citation.version_number}
                      </div>
                    )}
                  </li>
                ))}
                {suggestions.data?.length === 0 && <li className="text-slate-500">No applicable articles.</li>}
              </ul>
            </Card>
          )}

          {canWork && (
            <Card title="Timeline">
              <ul className="space-y-2 text-xs text-slate-600">
                {t.events.map((e) => (
                  <li key={e.event_id}>
                    <span className="font-medium">{e.event_type}</span>
                    {e.to_status && ` → ${e.to_status}`}
                    <div className="text-slate-400">{formatDateTime(e.created_at)}</div>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </div>

      <Modal
        open={dialog === 'escalate' || dialog === 'reopen'}
        title={dialog === 'escalate' ? 'Escalate ticket' : 'Reopen ticket'}
        onClose={() => setDialog(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={reason.trim().length < 3}
              onClick={() =>
                void run(() =>
                  dialog === 'escalate'
                    ? ticketService.escalate(t.ticket_id, reason)
                    : ticketService.reopen(t.ticket_id, reason),
                )
              }
            >
              Confirm
            </Button>
          </>
        }
      >
        <label className="block text-sm">
          <span className="text-slate-700">Reason</span>
          <textarea
            className="mt-1 h-24 w-full rounded-md border border-slate-300 px-3 py-2"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
      </Modal>

      <Modal
        open={dialog === 'resolve'}
        title="Resolve ticket"
        onClose={() => setDialog(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={summary.trim().length < 3 || resolutionText.trim().length < 3}
              onClick={() =>
                void run(() =>
                  ticketService.resolve(t.ticket_id, {
                    resolution_type: resolutionType,
                    summary,
                    resolution_text: resolutionText,
                  }),
                )
              }
            >
              Resolve
            </Button>
          </>
        }
      >
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-slate-700">Type</span>
            <select
              className="mt-1 w-full rounded-md border border-slate-300 px-2 py-2"
              value={resolutionType}
              onChange={(e) => setResolutionType(e.target.value)}
            >
              {RESOLUTION_TYPES.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-slate-700">Summary</span>
            <input
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2"
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-slate-700">Resolution details</span>
            <textarea
              className="mt-1 h-24 w-full rounded-md border border-slate-300 px-3 py-2"
              value={resolutionText}
              onChange={(e) => setResolutionText(e.target.value)}
            />
          </label>
        </div>
      </Modal>
    </div>
  );
}
