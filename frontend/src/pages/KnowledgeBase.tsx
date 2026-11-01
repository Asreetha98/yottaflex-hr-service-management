import { useState } from 'react';
import type { FormEvent } from 'react';
import Badge from '../components/common/Badge';
import Button from '../components/common/Button';
import Card from '../components/common/Card';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { useApi } from '../hooks/useApi';
import { errorMessage } from '../services/api';
import { policyService } from '../services/policyService';
import type { KnowledgeHit } from '../types';

const CATEGORIES = ['PAYROLL', 'LEAVE', 'BENEFITS', 'ONBOARDING'];

export default function KnowledgeBase() {
  const [category, setCategory] = useState('');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const articles = useApi(() => policyService.articles(category || undefined), [category]);

  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      setHits(await policyService.searchKnowledge(query, category || undefined));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-slate-900">Knowledge Base</h1>

      <Card>
        <form onSubmit={search} className="flex flex-wrap gap-3">
          <input
            className="min-w-64 flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            placeholder="Ask a question, e.g. how many sick leave days do I get?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className="rounded-md border border-slate-300 px-2 py-2 text-sm"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <Button type="submit" loading={searching}>
            Search
          </Button>
        </form>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </Card>

      {hits && (
        <Card title={`Search results (${hits.length})`}>
          {hits.length === 0 && <p className="text-sm text-slate-500">No applicable articles for your audience.</p>}
          <ul className="space-y-4">
            {hits.map((h) => (
              <li key={h.article_id} className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-900">{h.title}</span>
                  <Badge label={`${(h.confidence * 100).toFixed(0)}%`} tone="blue" />
                  {h.policy_backed && <Badge label="POLICY BACKED" tone="green" />}
                </div>
                <p className="mt-1 text-slate-700">{h.answer_snippet}</p>
                {h.citation && (
                  <p className="mt-1 text-xs text-slate-500">
                    Source: {h.citation.policy_title} v{h.citation.version_number}
                    {h.citation.section_reference && ` · ${h.citation.section_reference}`} ({h.citation.version_id})
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title="All articles">
        {articles.loading && <LoadingSpinner />}
        {articles.error && <p className="text-sm text-red-600">{articles.error}</p>}
        <ul className="divide-y divide-slate-100">
          {(articles.data?.items ?? []).map((a) => (
            <li key={a.article_id} className="py-3 text-sm">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-slate-400">{a.article_id}</span>
                <span className="font-medium text-slate-900">{a.title}</span>
                {a.category_code && <Badge label={a.category_code} tone="blue" />}
              </div>
              {a.summary && <p className="mt-1 text-slate-600">{a.summary}</p>}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
