import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import api from '../lib/api';
import type { DashboardSummary } from '../lib/types';

export default function DashboardPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => (await api.get<DashboardSummary>('/dashboard/summary/')).data,
  });
  if (isLoading) return <p>Loading…</p>;
  if (isError || !data) return <p role="alert">Failed to load. Is the Django API running?</p>;
  return (
    <div>
      <h1>Dashboard</h1>
      <div className="kpis">
        <div className="kpi"><span>Spend</span><strong>€{data.spend.toFixed(2)}</strong></div>
        <div className="kpi"><span>Revenue</span><strong>€{data.revenue.toFixed(2)}</strong></div>
        <div className="kpi"><span>Orders</span><strong>{data.orders}</strong></div>
        <div className="kpi"><span>ROAS</span><strong>{data.roas}x</strong></div>
      </div>
      <h2>Revenue by campaign</h2>
      <div className="chart">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data.campaigns}>
            <XAxis dataKey="name" hide />
            <YAxis />
            <Tooltip />
            <Bar dataKey="revenue" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table>
        <thead><tr><th>Campaign</th><th>Status</th><th>Spend</th><th>Revenue</th><th>ROAS</th></tr></thead>
        <tbody>
          {data.campaigns.map((c) => (
            <tr key={c.id}><td>{c.name}</td><td>{c.status}</td><td>€{c.spend.toFixed(2)}</td><td>€{c.revenue.toFixed(2)}</td><td>{c.roas}x</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
