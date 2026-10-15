import { zodResolver } from '@hookform/resolvers/zod';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Plus, UploadCloud } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { downloadCsv, fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatCurrency, formatDate, formatPercent, formatRoas, toDateInputValue } from '@/lib/format';
import type { AdSpend, Campaign, Channel, DailyMetric, ImportResult } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { EmptyState } from '@/ui/empty-state';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/ui/tabs';

const PAGE_SIZE = 20;
// Default date for the add dialogs; computed once per page load.
const TODAY = toDateInputValue(new Date());

export default function ResultsPage() {
  return (
    <div>
      <PageHeader
        title="Results"
        description="Import, add and export daily metrics and ad spend. Invalid CSV rows are skipped and reported with their line number."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <ImportCard
          title="Metrics CSV"
          description="Daily revenue, orders, spend and CTR per campaign."
          columns={['campaign', 'date', 'revenue', 'orders', 'spend', 'ctr', 'roas (optional)']}
          sample={'campaign,date,revenue,orders,spend,ctr\n1,2026-10-01,120.00,4,40.00,0.4'}
          endpoint="/metrics/import-csv/"
          templateName="metrics-template.csv"
        />
        <ImportCard
          title="Spend CSV"
          description="Ad spend and delivery stats per campaign and channel."
          columns={['campaign', 'channel (optional)', 'date', 'spend', 'impressions', 'clicks', 'conversions']}
          sample={'campaign,channel,date,spend,impressions,clicks,conversions\n1,1,2026-10-01,30.00,1000,50,5'}
          endpoint="/spend/import-csv/"
          templateName="spend-template.csv"
        />
      </div>

      <Tabs defaultValue="metrics" className="mt-6">
        <TabsList>
          <TabsTrigger value="metrics">Daily metrics</TabsTrigger>
          <TabsTrigger value="spend">Ad spend</TabsTrigger>
        </TabsList>
        <TabsContent value="metrics">
          <MetricsSection />
        </TabsContent>
        <TabsContent value="spend">
          <SpendSection />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ImportCard({
  title,
  description,
  columns,
  sample,
  endpoint,
  templateName,
}: {
  title: string;
  description: string;
  columns: string[];
  sample: string;
  endpoint: string;
  templateName: string;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    setError(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const { data } = await api.post<ImportResult>(endpoint, fd);
      setResult(data);
    } catch (ex) {
      setError(getErrorMessage(ex, 'Upload failed.'));
    } finally {
      setBusy(false);
    }
  };

  const downloadSample = () => {
    const blob = new Blob([sample + '\n'], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = templateName;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Columns: <code className="rounded bg-muted px-1 py-0.5 font-mono">{columns.join(', ')}</code>{' '}
          <button onClick={downloadSample} className="font-medium text-primary hover:underline">
            Download template
          </button>
        </p>
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            void upload(e.dataTransfer.files?.[0]);
          }}
          className={
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ' +
            (dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 hover:bg-muted/50')
          }
        >
          <UploadCloud className="size-6 text-muted-foreground" aria-hidden />
          <span className="text-sm font-medium">{busy ? 'Importing…' : 'Drop a CSV here or click to choose'}</span>
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              void upload(file);
            }}
          />
        </label>
        {error && <Alert variant="destructive">{error}</Alert>}
        {result && (
          <Alert variant={result.error_count > 0 ? 'info' : 'success'}>
            <p>
              Imported: <strong>{result.created}</strong> new, <strong>{result.updated}</strong> updated.
              {result.error_count > 0 && (
                <>
                  {' '}
                  <strong>{result.error_count}</strong> row(s) skipped.
                </>
              )}
            </p>
          </Alert>
        )}
        {result && result.errors.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">Line</TableHead>
                <TableHead>Problem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.errors.map((e, i) => (
                <TableRow key={`${e.row}-${i}`}>
                  <TableCell className="tabular-nums">{e.row}</TableCell>
                  <TableCell className="text-destructive">{e.error}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function useCampaignOptions() {
  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 200 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 200, ordering: 'name' }),
  });
  const campaignNames = useMemo(
    () => new Map((campaigns.data?.results ?? []).map((c) => [c.id, c.name])),
    [campaigns.data],
  );
  return { campaigns: campaigns.data?.results ?? [], campaignNames };
}

function MetricsSection() {
  const qc = useQueryClient();
  const { campaigns, campaignNames } = useCampaignOptions();
  const [page, setPage] = useState(1);
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [addOpen, setAddOpen] = useState(false);

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      ordering: '-date',
      campaign: campaignFilter === 'all' ? undefined : Number(campaignFilter),
      date__gte: from || undefined,
      date__lte: to || undefined,
    }),
    [page, campaignFilter, from, to],
  );

  const list = useQuery({
    queryKey: qk.metrics(params),
    queryFn: () => fetchList<DailyMetric>('/metrics/', params),
    placeholderData: keepPreviousData,
  });

  const rows = list.data?.results ?? [];
  const hasFilters = campaignFilter !== 'all' || Boolean(from) || Boolean(to);

  const exportCsv = () =>
    downloadCsv(
      '/metrics/export-csv/',
      { campaign: params.campaign, date__gte: params.date__gte, date__lte: params.date__lte },
      'metrics.csv',
    ).catch((e) => toast.error(getErrorMessage(e, 'Export failed.')));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select
          value={campaignFilter}
          onValueChange={(v) => {
            setCampaignFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-48" aria-label="Filter by campaign">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All campaigns</SelectItem>
            {campaigns.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="date"
          className="w-40"
          aria-label="From date"
          value={from}
          onChange={(e) => {
            setFrom(e.target.value);
            setPage(1);
          }}
        />
        <Input
          type="date"
          className="w-40"
          aria-label="To date"
          value={to}
          onChange={(e) => {
            setTo(e.target.value);
            setPage(1);
          }}
        />
        <span className="flex-1" />
        <Button variant="outline" onClick={exportCsv}>
          <Download /> Export CSV
        </Button>
        <Button onClick={() => setAddOpen(true)}>
          <Plus /> Add row
        </Button>
      </div>

      {list.isLoading ? (
        <Skeleton className="h-56" />
      ) : rows.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No metrics match your filters' : 'No daily metrics yet'}
          description={hasFilters ? 'Widen the date range or clear the campaign filter.' : 'Import a CSV above or add a row manually.'}
          action={
            <Button onClick={() => setAddOpen(true)}>
              <Plus /> Add row
            </Button>
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Campaign</TableHead>
                <TableHead className="text-right">Revenue</TableHead>
                <TableHead className="text-right">Orders</TableHead>
                <TableHead className="text-right">Spend</TableHead>
                <TableHead className="text-right">CTR</TableHead>
                <TableHead className="text-right">ROAS</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{formatDate(m.date)}</TableCell>
                  <TableCell>
                    <Link to={`/campaigns/${m.campaign}`} className="text-primary hover:underline">
                      {campaignNames.get(m.campaign) ?? `#${m.campaign}`}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(m.revenue)}</TableCell>
                  <TableCell className="text-right tabular-nums">{m.orders}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(m.spend)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatPercent(m.ctr)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatRoas(m.roas)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}

      <AddMetricDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        campaigns={campaigns}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ['metrics'] });
          qc.invalidateQueries({ queryKey: ['dashboard'] });
        }}
      />
    </div>
  );
}

function SpendSection() {
  const qc = useQueryClient();
  const { campaigns, campaignNames } = useCampaignOptions();
  const channels = useQuery({
    queryKey: qk.channels,
    queryFn: () => fetchList<Channel>('/channels/', { page_size: 200, ordering: 'name' }),
  });
  const channelNames = useMemo(
    () => new Map((channels.data?.results ?? []).map((c) => [c.id, c.name])),
    [channels.data],
  );
  const [page, setPage] = useState(1);
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [channelFilter, setChannelFilter] = useState('all');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [addOpen, setAddOpen] = useState(false);

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      ordering: '-date',
      campaign: campaignFilter === 'all' ? undefined : Number(campaignFilter),
      channel: channelFilter === 'all' ? undefined : Number(channelFilter),
      date__gte: from || undefined,
      date__lte: to || undefined,
    }),
    [page, campaignFilter, channelFilter, from, to],
  );

  const list = useQuery({
    queryKey: qk.spend(params),
    queryFn: () => fetchList<AdSpend>('/spend/', params),
    placeholderData: keepPreviousData,
  });

  const rows = list.data?.results ?? [];
  const hasFilters = campaignFilter !== 'all' || channelFilter !== 'all' || Boolean(from) || Boolean(to);

  const exportCsv = () =>
    downloadCsv(
      '/spend/export-csv/',
      {
        campaign: params.campaign,
        channel: params.channel,
        date__gte: params.date__gte,
        date__lte: params.date__lte,
      },
      'spend.csv',
    ).catch((e) => toast.error(getErrorMessage(e, 'Export failed.')));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Select
          value={campaignFilter}
          onValueChange={(v) => {
            setCampaignFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-48" aria-label="Filter by campaign">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All campaigns</SelectItem>
            {campaigns.map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={channelFilter}
          onValueChange={(v) => {
            setChannelFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by channel">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All channels</SelectItem>
            {(channels.data?.results ?? []).map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="date"
          className="w-40"
          aria-label="From date"
          value={from}
          onChange={(e) => {
            setFrom(e.target.value);
            setPage(1);
          }}
        />
        <Input
          type="date"
          className="w-40"
          aria-label="To date"
          value={to}
          onChange={(e) => {
            setTo(e.target.value);
            setPage(1);
          }}
        />
        <span className="flex-1" />
        <Button variant="outline" onClick={exportCsv}>
          <Download /> Export CSV
        </Button>
        <Button onClick={() => setAddOpen(true)}>
          <Plus /> Add row
        </Button>
      </div>

      {list.isLoading ? (
        <Skeleton className="h-56" />
      ) : rows.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No spend rows match your filters' : 'No ad spend recorded yet'}
          description={hasFilters ? 'Widen the date range or clear a filter.' : 'Import a spend CSV above or add a row manually.'}
          action={
            <Button onClick={() => setAddOpen(true)}>
              <Plus /> Add row
            </Button>
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Campaign</TableHead>
                <TableHead>Channel</TableHead>
                <TableHead className="text-right">Spend</TableHead>
                <TableHead className="text-right">Impressions</TableHead>
                <TableHead className="text-right">Clicks</TableHead>
                <TableHead className="text-right">Conversions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((s) => (
                <TableRow key={s.id}>
                  <TableCell>{formatDate(s.date)}</TableCell>
                  <TableCell>
                    <Link to={`/campaigns/${s.campaign}`} className="text-primary hover:underline">
                      {campaignNames.get(s.campaign) ?? `#${s.campaign}`}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {s.channel != null ? (channelNames.get(s.channel) ?? `#${s.channel}`) : '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(s.spend)}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.impressions.toLocaleString()}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.clicks.toLocaleString()}</TableCell>
                  <TableCell className="text-right tabular-nums">{s.conversions.toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}

      <AddSpendDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        campaigns={campaigns}
        channels={channels.data?.results ?? []}
        onSaved={() => {
          qc.invalidateQueries({ queryKey: ['spend'] });
          qc.invalidateQueries({ queryKey: ['dashboard'] });
        }}
      />
    </div>
  );
}

const metricSchema = z.object({
  campaign: z.string().min(1, 'Choose a campaign.'),
  date: z.string().min(1, 'Pick a date.'),
  revenue: z.coerce.number().min(0, 'Must be 0 or more.'),
  orders: z.coerce.number().int('Whole numbers only.').min(0, 'Must be 0 or more.'),
  spend: z.coerce.number().min(0, 'Must be 0 or more.'),
  ctr: z.coerce.number().min(0, 'Must be 0 or more.'),
});

type MetricValues = z.infer<typeof metricSchema>;

function AddMetricDialog({
  open,
  onOpenChange,
  campaigns,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaigns: Campaign[];
  onSaved: () => void;
}) {
  const form = useForm<z.input<typeof metricSchema>, unknown, z.output<typeof metricSchema>>({
    resolver: zodResolver(metricSchema),
    defaultValues: {
      campaign: '',
      date: TODAY,
      revenue: 0,
      orders: 0,
      spend: 0,
      ctr: 0,
    },
  });
  const { control, register, handleSubmit, reset, formState: { errors } } = form;
  const revenue = Number(useWatch({ control, name: 'revenue' })) || 0;
  const spend = Number(useWatch({ control, name: 'spend' })) || 0;
  const roas = spend > 0 ? Math.round((revenue / spend) * 100) / 100 : 0;

  const save = useMutation({
    mutationFn: async (values: MetricValues) =>
      (
        await api.post('/metrics/', {
          campaign: Number(values.campaign),
          date: values.date,
          revenue: values.revenue,
          orders: values.orders,
          spend: values.spend,
          ctr: values.ctr,
          roas,
        })
      ).data,
    onSuccess: () => {
      onSaved();
      toast.success('Result added');
      onOpenChange(false);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (o) reset({ campaign: '', date: TODAY, revenue: 0, orders: 0, spend: 0, ctr: 0 });
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add daily result</DialogTitle>
          <DialogDescription>For a single campaign and day. ROAS is derived from revenue ÷ spend.</DialogDescription>
        </DialogHeader>
        <form id="metric-form" noValidate onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
          <Field label="Campaign" error={errors.campaign?.message}>
            <Controller
              control={control}
              name="campaign"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger aria-label="Campaign">
                    <SelectValue placeholder="Choose a campaign…" />
                  </SelectTrigger>
                  <SelectContent>
                    {campaigns.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date" htmlFor="metric-date" error={errors.date?.message}>
              <Input id="metric-date" type="date" {...register('date')} />
            </Field>
            <Field label="CTR (%)" htmlFor="metric-ctr" error={errors.ctr?.message}>
              <Input id="metric-ctr" type="number" step="0.01" {...register('ctr')} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Revenue (€)" htmlFor="metric-revenue" error={errors.revenue?.message}>
              <Input id="metric-revenue" type="number" step="0.01" {...register('revenue')} />
            </Field>
            <Field label="Spend (€)" htmlFor="metric-spend" error={errors.spend?.message}>
              <Input id="metric-spend" type="number" step="0.01" {...register('spend')} />
            </Field>
            <Field label="Orders" htmlFor="metric-orders" error={errors.orders?.message}>
              <Input id="metric-orders" type="number" {...register('orders')} />
            </Field>
          </div>
          <p className="text-xs text-muted-foreground">
            Derived ROAS: <span className="font-medium text-foreground">{formatRoas(roas)}</span>
          </p>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="metric-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Add result'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const spendSchema = z.object({
  campaign: z.string().min(1, 'Choose a campaign.'),
  channel: z.string(),
  date: z.string().min(1, 'Pick a date.'),
  spend: z.coerce.number().min(0, 'Must be 0 or more.'),
  impressions: z.coerce.number().int().min(0, 'Must be 0 or more.'),
  clicks: z.coerce.number().int().min(0, 'Must be 0 or more.'),
  conversions: z.coerce.number().int().min(0, 'Must be 0 or more.'),
});

type SpendValues = z.infer<typeof spendSchema>;

function AddSpendDialog({
  open,
  onOpenChange,
  campaigns,
  channels,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  campaigns: Campaign[];
  channels: Channel[];
  onSaved: () => void;
}) {
  const form = useForm<z.input<typeof spendSchema>, unknown, z.output<typeof spendSchema>>({
    resolver: zodResolver(spendSchema),
    defaultValues: {
      campaign: '',
      channel: '',
      date: TODAY,
      spend: 0,
      impressions: 0,
      clicks: 0,
      conversions: 0,
    },
  });
  const { control, register, handleSubmit, reset, formState: { errors } } = form;

  const save = useMutation({
    mutationFn: async (values: SpendValues) =>
      (
        await api.post('/spend/', {
          campaign: Number(values.campaign),
          channel: values.channel ? Number(values.channel) : null,
          date: values.date,
          spend: values.spend,
          impressions: values.impressions,
          clicks: values.clicks,
          conversions: values.conversions,
        })
      ).data,
    onSuccess: () => {
      onSaved();
      toast.success('Spend row added');
      onOpenChange(false);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o);
        if (o)
          reset({
            campaign: '',
            channel: '',
            date: TODAY,
            spend: 0,
            impressions: 0,
            clicks: 0,
            conversions: 0,
          });
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add ad spend</DialogTitle>
          <DialogDescription>One campaign, optionally one channel, one day.</DialogDescription>
        </DialogHeader>
        <form id="spend-form" noValidate onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Campaign" error={errors.campaign?.message}>
              <Controller
                control={control}
                name="campaign"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="Campaign">
                      <SelectValue placeholder="Choose a campaign…" />
                    </SelectTrigger>
                    <SelectContent>
                      {campaigns.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Channel" error={errors.channel?.message}>
              <Controller
                control={control}
                name="channel"
                render={({ field }) => (
                  <Select value={field.value || 'none'} onValueChange={(v) => field.onChange(v === 'none' ? '' : v)}>
                    <SelectTrigger aria-label="Channel">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No specific channel</SelectItem>
                      {channels.map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Date" htmlFor="spend-date" error={errors.date?.message}>
              <Input id="spend-date" type="date" {...register('date')} />
            </Field>
            <Field label="Spend (€)" htmlFor="spend-spend" error={errors.spend?.message}>
              <Input id="spend-spend" type="number" step="0.01" {...register('spend')} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Impressions" htmlFor="spend-impressions" error={errors.impressions?.message}>
              <Input id="spend-impressions" type="number" {...register('impressions')} />
            </Field>
            <Field label="Clicks" htmlFor="spend-clicks" error={errors.clicks?.message}>
              <Input id="spend-clicks" type="number" {...register('clicks')} />
            </Field>
            <Field label="Conversions" htmlFor="spend-conversions" error={errors.conversions?.message}>
              <Input id="spend-conversions" type="number" {...register('conversions')} />
            </Field>
          </div>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="spend-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : 'Add spend'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
