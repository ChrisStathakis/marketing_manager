import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Megaphone, Plus, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { CampaignFormFields, campaignPayload, useCampaignForm } from '@/components/CampaignForm';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatCurrency, formatDate } from '@/lib/format';
import type { Campaign } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { EmptyState } from '@/ui/empty-state';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { CampaignStatusBadge } from '@/ui/status-badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const PAGE_SIZE = 20;

export default function CampaignsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [status, setStatus] = useState<string>('all');
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch || undefined,
      status: status === 'all' ? undefined : status,
      ordering: '-created_at',
    }),
    [page, debouncedSearch, status],
  );

  const list = useQuery({
    queryKey: qk.campaigns(params),
    queryFn: () => fetchList<Campaign>('/campaigns/', params),
    placeholderData: keepPreviousData,
  });

  const create = useMutation({
    mutationFn: async (values: ReturnType<typeof campaignPayload>) =>
      (await api.post<Campaign>('/campaigns/', values)).data,
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: ['campaigns'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success(`Campaign "${created.name}" created`);
      setCreateOpen(false);
      create.reset();
    },
  });

  const rows = list.data?.results ?? [];
  const hasFilters = Boolean(debouncedSearch) || status !== 'all';

  return (
    <div>
      <PageHeader
        title="Campaigns"
        description="Plan, launch and track your basket campaigns."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus /> New campaign
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="pl-9"
            placeholder="Search campaigns…"
            aria-label="Search campaigns"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="planned">Planned</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="paused">Paused</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {list.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Megaphone}
          title={hasFilters ? 'No campaigns match your filters' : 'No campaigns yet'}
          description={
            hasFilters
              ? 'Try a different search term or clear the status filter.'
              : 'Create your first campaign to start planning content and tracking results.'
          }
          action={
            hasFilters ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch('');
                  setStatus('all');
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus /> New campaign
              </Button>
            )
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Campaign</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Budget</TableHead>
                <TableHead className="hidden md:table-cell">UTM campaign</TableHead>
                <TableHead className="hidden lg:table-cell">Starts</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="max-w-70">
                    <Link to={`/campaigns/${c.id}`} className="font-medium text-primary hover:underline">
                      {c.name}
                    </Link>
                    {c.objective && <p className="mt-0.5 truncate text-xs text-muted-foreground">{c.objective}</p>}
                  </TableCell>
                  <TableCell>
                    <CampaignStatusBadge status={c.status} />
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(c.budget)}</TableCell>
                  <TableCell className="hidden font-mono text-xs text-muted-foreground md:table-cell">
                    {c.utm_campaign || '—'}
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground lg:table-cell">{formatDate(c.start_date)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}

      <CreateCampaignDialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) create.reset();
        }}
        pending={create.isPending}
        error={create.isError ? getErrorMessage(create.error) : undefined}
        onSubmit={(values) => create.mutate(campaignPayload(values))}
      />
    </div>
  );
}

function CreateCampaignDialog({
  open,
  onOpenChange,
  pending,
  error,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  pending: boolean;
  error?: string;
  onSubmit: (values: Parameters<typeof campaignPayload>[0]) => void;
}) {
  const form = useCampaignForm();
  const handleSubmit = form.handleSubmit((values) => onSubmit(values));
  useEffect(() => {
    if (open) form.reset();
  }, [open, form]);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>New campaign</DialogTitle>
          <DialogDescription>Only the name is required — you can fill in the rest now or later.</DialogDescription>
        </DialogHeader>
        {error && (
          <Alert variant="destructive" className="mb-4">
            {error}
          </Alert>
        )}
        <form onSubmit={handleSubmit} noValidate id="create-campaign-form">
          <CampaignFormFields form={form} idPrefix="create-" />
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
            Cancel
          </Button>
          <Button type="submit" form="create-campaign-form" disabled={pending}>
            {pending ? 'Creating…' : 'Create campaign'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
