import { Suspense, lazy, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Euro, Megaphone, Percent, ShoppingCart } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { StatCard } from '@/components/StatCard';
import { fetchOne, qk } from '@/lib/data';
import { formatCurrency, formatDate, formatNumber, formatRoas } from '@/lib/format';
import type { DashboardSummary } from '@/lib/types';
import { buttonVariants } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { EmptyState } from '@/ui/empty-state';
import { Input } from '@/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { CampaignStatusBadge } from '@/ui/status-badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const PerformanceChart = lazy(() => import('@/components/charts/PerformanceChart'));

type Preset = '7' | '30' | '90' | 'all' | 'custom';

export default function DashboardPage() {
  const [preset, setPreset] = useState<Preset>('30');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const params = useMemo(() => {
    if (preset === 'custom') return { date__gte: from || undefined, date__lte: to || undefined };
    if (preset === 'all') return {};
    return { days: Number(preset) };
  }, [preset, from, to]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.dashboard(params),
    queryFn: () => fetchOne<DashboardSummary>('/dashboard/summary/', params),
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-48" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Failed to load the dashboard"
        description="Is the Django API running? Check the backend window and retry."
        action={
          <button className={buttonVariants({ variant: 'outline' })} onClick={() => refetch()}>
            Retry
          </button>
        }
      />
    );
  }

  const rangeLabel =
    data.range.start && data.range.end ? `${formatDate(data.range.start)} → ${formatDate(data.range.end)}` : 'All time';

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Spend, revenue and ROAS across all campaigns."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Select value={preset} onValueChange={(v) => setPreset(v as Preset)}>
              <SelectTrigger className="w-44" aria-label="Date range">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
                <SelectItem value="all">All time</SelectItem>
                <SelectItem value="custom">Custom range…</SelectItem>
              </SelectContent>
            </Select>
            {preset === 'custom' && (
              <>
                <Input
                  type="date"
                  className="w-40"
                  aria-label="From date"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
                <Input type="date" className="w-40" aria-label="To date" value={to} onChange={(e) => setTo(e.target.value)} />
              </>
            )}
          </div>
        }
      />

      <div className="enter-stagger grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Spend" value={formatCurrency(data.spend)} icon={Megaphone} delta={data.deltas.spend} />
        <StatCard label="Revenue" value={formatCurrency(data.revenue)} icon={Euro} delta={data.deltas.revenue} />
        <StatCard label="Orders" value={formatNumber(data.orders)} icon={ShoppingCart} delta={data.deltas.orders} />
        <StatCard label="ROAS" value={formatRoas(data.roas)} icon={Percent} delta={data.deltas.roas} hint="Revenue ÷ spend" featured />
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Revenue vs spend</CardTitle>
          <CardDescription>Daily totals for {rangeLabel.toLowerCase()}.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.series.length > 0 ? (
            <Suspense fallback={<Skeleton className="h-70 w-full" />}>
              <PerformanceChart data={data.series} />
            </Suspense>
          ) : (
            <EmptyState
              title="No results in this range"
              description="Import a metrics CSV, add a daily result, or widen the date range."
              action={
                <Link to="/results" className={buttonVariants()}>
                  Record results
                </Link>
              }
            />
          )}
        </CardContent>
      </Card>

      <h2 className="mt-6 mb-3 text-lg font-semibold tracking-tight">Campaign performance</h2>
      {data.campaigns.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Campaign</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Spend</TableHead>
              <TableHead className="text-right">Revenue</TableHead>
              <TableHead className="text-right">Orders</TableHead>
              <TableHead className="text-right">ROAS</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.campaigns.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  <Link to={`/campaigns/${c.id}`} className="font-medium text-primary hover:underline">
                    {c.name}
                  </Link>
                </TableCell>
                <TableCell>
                  <CampaignStatusBadge status={c.status} />
                </TableCell>
                <TableCell className="text-right tabular-nums">{formatCurrency(c.spend)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatCurrency(c.revenue)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatNumber(c.orders)}</TableCell>
                <TableCell className="text-right tabular-nums">{formatRoas(c.roas)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <EmptyState
          title="No campaigns yet"
          description="Create your first campaign to start tracking spend and results."
          action={
            <Link to="/campaigns" className={buttonVariants()}>
              Go to campaigns
            </Link>
          }
        />
      )}
    </div>
  );
}
