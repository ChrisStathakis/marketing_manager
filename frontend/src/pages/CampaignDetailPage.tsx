import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { ArrowLeft, CheckCircle2, Circle, Download, FileText, Lightbulb, ListTodo, Pause, Pencil, Play, Plus, Sparkles, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { CampaignDialog } from '@/components/CampaignDialog';
import { ContentItemDialog } from '@/components/ContentItemDialog';
import { SuggestionCard } from '@/components/SuggestionCard';
import api from '@/lib/api';
import { fetchList, fetchOne, qk, downloadCsv } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatCurrency, formatDate, formatDateTime, formatPercent, formatRoas, toDateInputValue } from '@/lib/format';
import type { Campaign, CampaignStatus, ContentItem, DailyMetric, Suggestion, Task } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Badge } from '@/ui/badge';
import { Button, buttonVariants } from '@/ui/button';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/ui/dropdown-menu';
import { EmptyState } from '@/ui/empty-state';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Skeleton } from '@/ui/skeleton';
import { CampaignStatusBadge, ContentStatusBadge } from '@/ui/status-badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/ui/tabs';

// Date comparison for overdue badges; computed once per page load.
const TODAY = toDateInputValue(new Date());

export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = Number(params.id);
  const valid = Number.isFinite(campaignId) && campaignId > 0;
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const campaign = useQuery({
    queryKey: qk.campaign(campaignId),
    queryFn: () => fetchOne<Campaign>(`/campaigns/${campaignId}/`),
    enabled: valid,
  });

  const setStatus = useMutation({
    mutationFn: async (next: CampaignStatus) => (await api.patch(`/campaigns/${campaignId}/`, { status: next })).data,
    onSuccess: (_data, next) => {
      qc.invalidateQueries({ queryKey: ['campaign', campaignId] });
      qc.invalidateQueries({ queryKey: ['campaigns'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success(`Campaign marked ${next}`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: async () => api.delete(`/campaigns/${campaignId}/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['campaigns'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success('Campaign deleted');
      navigate('/campaigns');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  if (!valid) return <InvalidCampaign />;
  if (campaign.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (campaign.isError || !campaign.data) return <InvalidCampaign />;

  const c = campaign.data;
  return (
    <div>
      <Link to="/campaigns" className="mb-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Campaigns
      </Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold tracking-tight">{c.name}</h1>
            <CampaignStatusBadge status={c.status} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Budget {formatCurrency(c.budget)}
            <span className="mx-1.5">·</span>
            {formatDate(c.start_date)} → {formatDate(c.end_date)}
            {c.utm_campaign && (
              <>
                <span className="mx-1.5">·</span>
                <span className="font-mono text-xs">utm_campaign={c.utm_campaign}</span>
              </>
            )}
          </p>
          {c.objective && <p className="mt-2 max-w-2xl text-sm">{c.objective}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {c.status === 'active' ? (
            <Button variant="outline" onClick={() => setStatus.mutate('paused')} disabled={setStatus.isPending}>
              <Pause /> Pause
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setStatus.mutate('active')} disabled={setStatus.isPending}>
              <Play /> Activate
            </Button>
          )}
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil /> Edit
          </Button>
          <Button variant="ghost" className="text-destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 /> Delete
          </Button>
        </div>
      </div>

      <Tabs defaultValue="results">
        <TabsList>
          <TabsTrigger value="results">Results</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="tasks">Tasks</TabsTrigger>
          <TabsTrigger value="suggestions">Suggestions</TabsTrigger>
        </TabsList>
        <TabsContent value="results">
          <ResultsTab campaignId={campaignId} />
        </TabsContent>
        <TabsContent value="content">
          <ContentTab campaignId={campaignId} />
        </TabsContent>
        <TabsContent value="tasks">
          <TasksTab campaignId={campaignId} />
        </TabsContent>
        <TabsContent value="suggestions">
          <SuggestionsTab campaignId={campaignId} />
        </TabsContent>
      </Tabs>

      <CampaignDialog open={editOpen} onOpenChange={setEditOpen} campaign={campaign.data} />
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete campaign?"
        description={`"${campaign.data.name}" and its results, content, tasks and suggestions will be removed permanently.`}
        confirmLabel="Delete"
        destructive
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

function ContentTab({ campaignId }: { campaignId: number }) {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [dialog, setDialog] = useState<{ open: boolean; item: ContentItem | null }>({ open: false, item: null });
  const [deleting, setDeleting] = useState<ContentItem | null>(null);
  const pageSize = 25;
  const params = { campaign: campaignId, page, page_size: pageSize, ordering: '-publish_at' };
  const list = useQuery({
    queryKey: qk.content(params),
    queryFn: () => fetchList<ContentItem>('/content/', params),
    placeholderData: keepPreviousData,
  });
  const remove = useMutation({
    mutationFn: async (item: ContentItem) => api.delete(`/content/${item.id}/`),
    onSuccess: () => {
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ['content'] });
      toast.success('Content item deleted');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
  const rows = list.data?.results ?? [];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Planned and published content for this campaign{list.data ? ` (${list.data.count})` : ''}.
        </p>
        <Button size="sm" onClick={() => setDialog({ open: true, item: null })}>
          <Plus /> New content
        </Button>
      </div>
      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No content planned"
          description="Plan the posts, stories and ads that will run for this campaign."
          action={<Button onClick={() => setDialog({ open: true, item: null })}>New content</Button>}
        />
      ) : (
        <>
          <ul className="grid gap-2">
            {rows.map((item) => (
              <li key={item.id} className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-2.5">
                <FileText className="size-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{formatDateTime(item.publish_at)}</p>
                </div>
                <ContentStatusBadge status={item.status} />
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" aria-label="Content actions">
                      ⋯
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onSelect={() => setDialog({ open: true, item })}>
                      <Pencil /> Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(item)}>
                      <Trash2 /> Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={pageSize} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}

      <ContentItemDialog
        open={dialog.open}
        onOpenChange={(open) => setDialog((s) => ({ ...s, open }))}
        item={dialog.item}
        defaultCampaignId={campaignId}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete content item?"
        description={deleting ? `"${deleting.title}" will be removed permanently.` : undefined}
        confirmLabel="Delete"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  );
}

function InvalidCampaign() {
  return (
    <EmptyState
      title="Campaign not found"
      description="It may have been deleted, or the link is wrong."
      action={
        <Link to="/campaigns" className={buttonVariants()}>
          All campaigns
        </Link>
      }
    />
  );
}

function ResultsTab({ campaignId }: { campaignId: number }) {
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const params = { campaign: campaignId, page, page_size: pageSize, ordering: '-date' };
  const list = useQuery({
    queryKey: qk.metrics(params),
    queryFn: () => fetchList<DailyMetric>('/metrics/', params),
    placeholderData: keepPreviousData,
  });
  const rows = list.data?.results ?? [];

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          Daily metrics for this campaign{list.data ? ` (${list.data.count} rows)` : ''}.
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() =>
              downloadCsv('/metrics/export-csv/', { campaign: campaignId }, 'campaign-metrics.csv').catch((e) =>
                toast.error(getErrorMessage(e, 'Export failed.')),
              )
            }
          >
            <Download /> Export CSV
          </Button>
          <Link to="/results" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
            Import CSV
          </Link>
        </div>
      </div>
      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Lightbulb}
          title="No results yet"
          description="Import a metrics CSV or add daily rows to see performance here."
          action={
            <Link to="/results" className={buttonVariants()}>
              Record results
            </Link>
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
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
                  <TableCell className="text-right tabular-nums">{formatCurrency(m.revenue)}</TableCell>
                  <TableCell className="text-right tabular-nums">{m.orders}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(m.spend)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatPercent(m.ctr)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatRoas(m.roas)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={pageSize} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}

function TasksTab({ campaignId }: { campaignId: number }) {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [deleting, setDeleting] = useState<Task | null>(null);
  const pageSize = 25;
  const params = { campaign: campaignId, page, page_size: pageSize, ordering: 'due_date' };
  const list = useQuery({
    queryKey: qk.tasks(params),
    queryFn: () => fetchList<Task>('/tasks/', params),
    placeholderData: keepPreviousData,
  });
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tasks'] });
    qc.invalidateQueries({ queryKey: ['dashboard'] });
  };

  const create = useMutation({
    mutationFn: async () =>
      api.post('/tasks/', { campaign: campaignId, title: title.trim(), due_date: dueDate || null }),
    onSuccess: () => {
      setTitle('');
      setDueDate('');
      invalidate();
      toast.success('Task added');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const toggle = useMutation({
    mutationFn: async (task: Task) => api.patch(`/tasks/${task.id}/`, { done: !task.done }),
    onSuccess: invalidate,
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: async (task: Task) => api.delete(`/tasks/${task.id}/`),
    onSuccess: () => {
      setDeleting(null);
      invalidate();
      toast.success('Task deleted');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const rows = list.data?.results ?? [];

  return (
    <div>
      <form
        className="mb-4 flex flex-wrap items-end gap-2 rounded-xl border border-border bg-card p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) create.mutate();
        }}
      >
        <div className="min-w-48 flex-1">
          <Input
            placeholder="New task, e.g. Brief 3 TikTok videos"
            aria-label="Task title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <Input
          type="date"
          className="w-40"
          aria-label="Due date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
        />
        <Button type="submit" disabled={!title.trim() || create.isPending}>
          <Plus /> Add task
        </Button>
      </form>

      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : rows.length === 0 ? (
        <EmptyState icon={ListTodo} title="No tasks yet" description="Add follow-ups here to keep the campaign moving." />
      ) : (
        <>
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            {rows.map((t) => {
              const overdue = !t.done && t.due_date && t.due_date < TODAY;
              return (
                <li key={t.id} className="flex items-center gap-3 px-4 py-2.5">
                  <button
                    className="shrink-0 text-muted-foreground transition-colors hover:text-primary"
                    aria-label={t.done ? 'Mark as not done' : 'Mark as done'}
                    onClick={() => toggle.mutate(t)}
                  >
                    {t.done ? <CheckCircle2 className="size-5 text-success" /> : <Circle className="size-5" />}
                  </button>
                  <span className={t.done ? 'flex-1 text-muted-foreground line-through' : 'flex-1'}>{t.title}</span>
                  {t.due_date && (
                    <span className="hidden sm:block">
                      <Badge variant={overdue ? 'destructive' : 'outline'}>
                        {overdue ? `Overdue · ${formatDate(t.due_date)}` : formatDate(t.due_date)}
                      </Badge>
                    </span>
                  )}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" aria-label="Task actions">
                        ⋯
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(t)}>
                        <Trash2 /> Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              );
            })}
          </ul>
          <Pagination page={page} pageSize={pageSize} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete task?"
        description={deleting ? `"${deleting.title}" will be removed permanently.` : undefined}
        confirmLabel="Delete"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  );
}

function SuggestionsTab({ campaignId }: { campaignId: number }) {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const params = { campaign: campaignId, page, page_size: pageSize, ordering: '-created_at' };
  const list = useQuery({
    queryKey: qk.suggestions(params),
    queryFn: () => fetchList<Suggestion>('/suggestions/', params),
    placeholderData: keepPreviousData,
  });

  const generate = useMutation({
    mutationFn: async (kind: 'rule' | 'ai') =>
      api.post(`/suggestions/generate${kind === 'ai' ? '-ai' : ''}/`, { campaign: campaignId }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['suggestions'] });
      const count = Array.isArray(res.data) ? res.data.length : 1;
      toast.success(`${count} suggestion${count === 1 ? '' : 's'} generated`);
    },
  });

  const aiNeedsKey =
    axios.isAxiosError(generate.error) && generate.error.response?.status === 501;

  const rows = list.data?.results ?? [];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button onClick={() => generate.mutate('rule')} disabled={generate.isPending}>
          {generate.isPending ? 'Generating…' : 'Generate rules'}
        </Button>
        <Button variant="outline" onClick={() => generate.mutate('ai')} disabled={generate.isPending}>
          <Sparkles /> Generate AI
        </Button>
        <p className="text-xs text-muted-foreground">AI needs OPENAI_API_KEY configured on the backend.</p>
      </div>
      {generate.isError && (
        <Alert variant={aiNeedsKey ? 'info' : 'destructive'} className="mb-4">
          {aiNeedsKey
            ? 'AI suggestions are not configured. Set OPENAI_API_KEY in backend/.env and restart Django — rule suggestions work without it.'
            : getErrorMessage(generate.error)}
        </Alert>
      )}

      {list.isLoading ? (
        <Skeleton className="h-40" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No suggestions yet"
          description="Generate rule-based next steps from your latest metrics — no API key needed."
          action={<Button onClick={() => generate.mutate('rule')}>Generate rules</Button>}
        />
      ) : (
        <>
          <ul className="grid gap-3">
            {rows.map((s) => (
              <li key={s.id}>
                <SuggestionCard suggestion={s} linkCampaign={false} />
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={pageSize} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
