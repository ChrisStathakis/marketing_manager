import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import api from '../lib/api';
import type { Campaign, Paginated } from '../lib/types';

export default function CampaignsPage() {
  const [name, setName] = useState('');
  const [budget, setBudget] = useState('500');
  const list = useQuery({
    queryKey: ['campaigns'],
    queryFn: async () => (await api.get<Paginated<Campaign> | Campaign[]>('/campaigns/')).data,
  });
  const rows: Campaign[] = Array.isArray(list.data) ? list.data : (list.data?.results ?? []);
  return (
    <div>
      <h1>Campaigns</h1>
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          await api.post('/campaigns/', { name, budget });
          setName('');
          list.refetch();
        }}
      >
        <input aria-label="Campaign name" placeholder="New campaign name" value={name} onChange={(e) => setName(e.target.value)} required />
        <input aria-label="Budget" value={budget} onChange={(e) => setBudget(e.target.value)} inputMode="decimal" />
        <button type="submit">Create</button>
      </form>
      {list.isLoading ? <p>Loading…</p> : (
        <table>
          <thead><tr><th>Name</th><th>Status</th><th>Budget</th><th>UTM</th><th /></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td><td>{c.status}</td><td>€{c.budget}</td><td>{c.utm_campaign}</td>
                <td><Link to={`/campaigns/${c.id}`}>Open</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
