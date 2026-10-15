import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import api from '../lib/api';
import type { Campaign, DailyMetric, Paginated, Suggestion, Task } from '../lib/types';

const asList = <T,>(d: Paginated<T> | T[] | undefined): T[] =>
  Array.isArray(d) ? d : (d?.results ?? []);

export default function CampaignDetailPage() {
  const { id } = useParams();
  const qc = useQueryClient();
  const campaign = useQuery({
    queryKey: ['campaign', id],
    queryFn: async () => (await api.get<Campaign>(`/campaigns/${id}/`)).data,
  });
  const metrics = useQuery({
    queryKey: ['metrics', id],
    queryFn: async () => (await api.get<Paginated<DailyMetric> | DailyMetric[]>(`/metrics/?campaign=${id}`)).data,
  });
  const tasks = useQuery({
    queryKey: ['tasks', id],
    queryFn: async () => (await api.get<Paginated<Task> | Task[]>(`/tasks/?campaign=${id}`)).data,
  });
  const suggestions = useQuery({
    queryKey: ['suggestions', id],
    queryFn: async () => (await api.get<Paginated<Suggestion> | Suggestion[]>(`/suggestions/?campaign=${id}`)).data,
  });
  const gen = useMutation({
    mutationFn: async (kind: 'rule' | 'ai') =>
      (await api.post(`/suggestions/generate${kind === 'ai' ? '-ai' : ''}/`, { campaign: Number(id) })).data,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['suggestions', id] }); },
  });
  if (campaign.isLoading) return <p>Loading…</p>;
  if (!campaign.data) return <p role="alert">Not found.</p>;
  return (
    <div>
      <h1>{campaign.data.name}</h1>
      <p>Status: {campaign.data.status} · Budget: €{campaign.data.budget}</p>
      <div className="grid2">
        <section>
          <h2>Results</h2>
          <table>
            <thead><tr><th>Date</th><th>Revenue</th><th>Orders</th><th>Spend</th><th>ROAS</th></tr></thead>
            <tbody>
              {asList(metrics.data).map((m) => (
                <tr key={m.id}><td>{m.date}</td><td>€{m.revenue}</td><td>{m.orders}</td><td>€{m.spend}</td><td>{m.roas}</td></tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>
          <h2>Tasks</h2>
          <ul>{asList(tasks.data).map((t) => <li key={t.id}>[ {t.done ? 'x' : ' '} ] {t.title}</li>)}</ul>
          <h2>Suggestions</h2>
          <div className="row">
            <button onClick={() => gen.mutate('rule')} disabled={gen.isPending}>Generate rules</button>
            <button onClick={() => gen.mutate('ai')} disabled={gen.isPending}>Generate AI</button>
          </div>
          {gen.isError && <p role="alert" className="error">AI needs OPENAI_API_KEY on the backend; rules still work.</p>}
          <ul>{asList(suggestions.data).map((s) => <li key={s.id}><strong>[{s.kind}] {s.title}</strong> — {s.text}</li>)}</ul>
        </section>
      </div>
    </div>
  );
}
