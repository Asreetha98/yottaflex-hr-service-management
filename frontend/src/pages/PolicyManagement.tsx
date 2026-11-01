import { useState } from 'react';
import type { FormEvent } from 'react';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Modal from '../components/common/Modal';
import Table from '../components/common/Table';
import type { Column } from '../components/common/Table';
import { useApi } from '../hooks/useApi';
import { api, errorMessage } from '../services/api';
import { policyService } from '../services/policyService';
import type { PolicyDocument, PolicyValidity, PolicyVersion } from '../types';

interface Department {
  department_id: string;
  name: string;
}

export default function PolicyManagement() {
  const policies = useApi(() => policyService.list(), []);
  const departments = useApi(async () => (await api.get<Department[]>('/employees/departments')).data, []);
  const [selected, setSelected] = useState<PolicyDocument | null>(null);
  const versions = useApi(
    () => (selected ? policyService.versions(selected.policy_id) : Promise.resolve([] as PolicyVersion[])),
    [selected?.policy_id],
  );
  const [referenceDate, setReferenceDate] = useState('');
  const [validity, setValidity] = useState<PolicyValidity | null>(null);

  const [showPolicy, setShowPolicy] = useState(false);
  const [showVersion, setShowVersion] = useState(false);
  const [title, setTitle] = useState('');
  const [deptId, setDeptId] = useState('');
  const [description, setDescription] = useState('');
  const [vTitle, setVTitle] = useState('');
  const [vContent, setVContent] = useState('');
  const [vFrom, setVFrom] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const guard = async (action: () => Promise<unknown>, onDone?: () => void) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onDone?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const createPolicy = (e: FormEvent) => {
    e.preventDefault();
    void guard(
      () => policyService.create(title, deptId || departments.data?.[0]?.department_id || '', description),
      () => {
        setShowPolicy(false);
        setTitle('');
        setDescription('');
        policies.reload();
      },
    );
  };

  const createVersion = (e: FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    void guard(
      () =>
        policyService.createVersion(selected.policy_id, {
          title: vTitle,
          content: vContent,
          effective_from: vFrom || undefined,
        }),
      () => {
        setShowVersion(false);
        setVTitle('');
        setVContent('');
        setVFrom('');
        versions.reload();
      },
    );
  };

  const checkEffective = () => {
    if (!selected) return;
    void guard(
      async () => setValidity(await policyService.effective(selected.policy_id, referenceDate || undefined)),
    );
  };

  const policyColumns: Column<PolicyDocument>[] = [
    { key: 'id', header: 'Policy', render: (p) => <span className="font-mono text-xs">{p.policy_id}</span> },
    { key: 'title', header: 'Title', render: (p) => p.title },
    { key: 'status', header: 'Status', render: (p) => <Badge label={p.status} /> },
  ];

  const versionColumns: Column<PolicyVersion>[] = [
    { key: 'id', header: 'Version', render: (v) => <span className="font-mono text-xs">{v.version_id}</span> },
    { key: 'n', header: '#', render: (v) => v.version_number },
    { key: 'status', header: 'Status', render: (v) => <Badge label={v.status} /> },
    { key: 'from', header: 'Effective from', render: (v) => v.effective_from ?? '—' },
    { key: 'to', header: 'Effective to', render: (v) => v.effective_to ?? '—' },
    {
      key: 'actions',
      header: '',
      render: (v) => (
        <div className="flex gap-2">
          {v.status === 'DRAFT' && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void guard(() => policyService.publish(v.version_id), versions.reload)}
            >
              Publish
            </Button>
          )}
          {v.status === 'PUBLISHED' && (
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => void guard(() => policyService.archive(v.version_id), versions.reload)}
            >
              Archive
            </Button>
          )}
        </div>
      ),
    },
  ];

  const input = 'mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Policy Management</h1>
        <Button onClick={() => setShowPolicy(true)}>New policy</Button>
      </div>
      {error && <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Policies">
          {policies.loading && <LoadingSpinner />}
          {policies.data && (
            <Table
              columns={policyColumns}
              rows={policies.data.items}
              rowKey={(p) => p.policy_id}
              onRowClick={(p) => {
                setSelected(p);
                setValidity(null);
              }}
            />
          )}
        </Card>

        <Card
          title={selected ? `Versions · ${selected.title}` : 'Versions'}
          actions={
            selected && (
              <Button variant="secondary" onClick={() => setShowVersion(true)}>
                New version
              </Button>
            )
          }
        >
          {!selected && <p className="text-sm text-slate-500">Select a policy to see its versions.</p>}
          {selected && versions.loading && <LoadingSpinner />}
          {selected && versions.data && (
            <>
              <Table columns={versionColumns} rows={versions.data} rowKey={(v) => v.version_id} />
              <div className="mt-4 flex items-end gap-2 border-t border-slate-100 pt-3">
                <label className="text-sm">
                  <span className="text-slate-600">Effective on</span>
                  <input
                    type="date"
                    className="mt-1 block rounded-md border border-slate-300 px-2 py-1.5"
                    value={referenceDate}
                    onChange={(e) => setReferenceDate(e.target.value)}
                  />
                </label>
                <Button variant="secondary" onClick={checkEffective}>
                  Resolve effective version
                </Button>
              </div>
              {validity && (
                <div className="mt-3 space-y-1 rounded-md bg-slate-50 p-3 text-xs text-slate-700">
                  <div>
                    <strong>Effective:</strong> {validity.version_id ?? validity.exception_code}
                  </div>
                  <div>Latest created: {validity.latest_created ?? '—'}</div>
                  <div>Latest published: {validity.latest_published ?? '—'}</div>
                  <div>Currently effective: {validity.currently_effective ?? '—'}</div>
                  <div>Historically effective: {validity.historically_effective ?? '—'}</div>
                  <div className="text-slate-500">{validity.explanation}</div>
                </div>
              )}
            </>
          )}
        </Card>
      </div>

      <Modal
        open={showPolicy}
        title="New policy"
        onClose={() => setShowPolicy(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowPolicy(false)}>
              Cancel
            </Button>
            <Button type="submit" form="policy-form" loading={busy}>
              Create
            </Button>
          </>
        }
      >
        <form id="policy-form" onSubmit={createPolicy} className="space-y-3">
          <label className="block text-sm">
            Title
            <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} required minLength={3} />
          </label>
          <label className="block text-sm">
            Owner department
            <select className={input} value={deptId} onChange={(e) => setDeptId(e.target.value)}>
              {(departments.data ?? []).map((d) => (
                <option key={d.department_id} value={d.department_id}>
                  {d.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Description
            <textarea className={input} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
        </form>
      </Modal>

      <Modal
        open={showVersion}
        title="New policy version (draft)"
        onClose={() => setShowVersion(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setShowVersion(false)}>
              Cancel
            </Button>
            <Button type="submit" form="version-form" loading={busy}>
              Create draft
            </Button>
          </>
        }
      >
        <form id="version-form" onSubmit={createVersion} className="space-y-3">
          <label className="block text-sm">
            Title
            <input className={input} value={vTitle} onChange={(e) => setVTitle(e.target.value)} required minLength={3} />
          </label>
          <label className="block text-sm">
            Effective from
            <input type="date" className={input} value={vFrom} onChange={(e) => setVFrom(e.target.value)} />
          </label>
          <label className="block text-sm">
            Content
            <textarea
              className={`${input} h-40`}
              value={vContent}
              onChange={(e) => setVContent(e.target.value)}
              required
              minLength={3}
            />
          </label>
        </form>
      </Modal>
    </div>
  );
}
