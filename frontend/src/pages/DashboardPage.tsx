import { Suspense, lazy } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Euro, Megaphone, Percent, ShoppingCart } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { StatCard } from '@/components/StatCard';
import { fetchOne, qk } from '@/lib/data';
import { formatCurrency, formatNumber, formatRoas } from '@/lib/format';
import type { DashboardSummary } from '@/lib/types';
import { buttonVariants } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { CampaignStatusBadge } from '@/ui/status-badge';
import { EmptyState } from '@/ui/empty-state';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const RevenueBarChart = lazy(() => import('@/components/charts/RevenueBarChart'));

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: qk.dashboard(),
    queryFn: () => fetchOne<DashboardSummary>('/dashboard/summary/'),
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

  const chartData = data.campaigns.filter((c) => c.revenue > 0).map((c) => ({ name: c.name, revenue: c.revenue }));

  return (
    <div>
      <PageHeader title="Dashboard" description="Spend, revenue and ROAS across all campaigns." />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Spend" value={formatCurrency(data.spend)} icon={Megaphone} />
        <StatCard label="Revenue" value={formatCurrency(data.revenue)} icon={Euro} />
        <StatCard label="Orders" value={formatNumber(data.orders)} icon={ShoppingCart} />
        <StatCard label="ROAS" value={formatRoas(data.roas)} icon={Percent} hint="Revenue ÷ spend" />
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Revenue by campaign</CardTitle>
          <CardDescription>Top campaigns with recorded results.</CardDescription>
        </CardHeader>
        <CardContent>
          {chartData.length > 0 ? (
            <Suspense fallback={<Skeleton className="h-70 w-full" />}>
              <RevenueBarChart data={chartData} />
            </Suspense>
          ) : (
            <EmptyState
              title="No results recorded yet"
              description="Import a metrics CSV or add a daily result to see the chart."
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
