import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import type { Paginated, Suggestion } from '../lib/types';

export default function SuggestionsPage() {
  const { data } = useQuery({
    queryKey: ['suggestions-all'],
    queryFn: async () => (await api.get<Paginated<Suggestion> | Suggestion[]>('/suggestions/?ordering=-created_at')).data,
  });
  const rows = Array.isArray(data) ? data : (data?.results ?? []);
  return (
    <div>
      <h1>Next-step suggestions</h1>
      <ul className="cards">
        {rows.map((s) => (
          <li key={s.id}><strong>[{s.kind}] {s.title}</strong><p>{s.text}</p><small>campaign {s.campaign}</small></li>
        ))}
      </ul>
    </div>
  );
}
