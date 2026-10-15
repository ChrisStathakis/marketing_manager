import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, CheckCircle2, Circle, Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatDate, toDateInputValue } from '@/lib/format';
import type { Campaign, Task } from '@/lib/types';
import { Badge } from '@/ui/badge';
import { Button } from '@/ui/button';
import { EmptyState } from '@/ui/empty-state';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const PAGE_SIZE = 20;
// Date comparison for overdue badges; computed once per page load.
const TODAY = toDateInputValue(new Date());

export default function CalendarPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [done, setDone] = useState('open');
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [title, setTitle] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [newCampaign, setNewCampaign] = useState('none');

  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 200 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 200, ordering: 'name' }),
  });
  const campaignNames = useMemo(
    () => new Map((campaigns.data?.results ?? []).map((c) => [c.id, c.name])),
    [campaigns.data],
  );

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      ordering: 'due_date',
      done: done === 'all' ? undefined : done === 'done',
      campaign: campaignFilter === 'all' ? undefined : Number(campaignFilter),
    }),
    [page, done, campaignFilter],
  );

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
      api.post('/tasks/', {
        title: title.trim(),
        due_date: dueDate || null,
        campaign: newCampaign === 'none' ? null : Number(newCampaign),
      }),
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

  const rows = list.data?.results ?? [];

  return (
    <div>
      <PageHeader title="Plans & calendar" description="Every follow-up across campaigns. The month grid arrives in the next update." />

      <form
        className="mb-4 flex flex-wrap items-end gap-2 rounded-xl border border-border bg-card p-3"
        onSubmit={(e) => {
          e.preventDefault();
          if (title.trim()) create.mutate();
        }}
      >
        <div className="min-w-52 flex-1">
          <Input
            placeholder="New task, e.g. Schedule week-3 posts"
            aria-label="Task title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </div>
        <Select value={newCampaign} onValueChange={setNewCampaign}>
          <SelectTrigger className="w-44" aria-label="Campaign">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="none">No campaign</SelectItem>
            {(campaigns.data?.results ?? []).map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="date"
          className="w-40"
          aria-label="Due date"
          value={dueDate}
          onChange={(e) => setDueDate(e.target.value)}
        />
        <Button type="submit" disabled={!title.trim() || create.isPending}>
          <Plus /> Add
        </Button>
      </form>

      <div className="mb-4 flex flex-wrap gap-2">
        <Select
          value={done}
          onValueChange={(v) => {
            setDone(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-36" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="open">Open tasks</SelectItem>
            <SelectItem value="done">Done</SelectItem>
            <SelectItem value="all">All tasks</SelectItem>
          </SelectContent>
        </Select>
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
            {(campaigns.data?.results ?? []).map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {list.isLoading ? (
        <Skeleton className="h-56" />
      ) : rows.length === 0 ? (
        <EmptyState icon={CalendarDays} title="Nothing scheduled" description="Add a task above to start planning." />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10" />
                <TableHead>Task</TableHead>
                <TableHead>Campaign</TableHead>
                <TableHead>Due</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((t) => {
                const overdue = !t.done && t.due_date && t.due_date < TODAY;
                return (
                  <TableRow key={t.id}>
                    <TableCell>
                      <button
                        className="text-muted-foreground transition-colors hover:text-primary"
                        aria-label={t.done ? 'Mark as not done' : 'Mark as done'}
                        onClick={() => toggle.mutate(t)}
                      >
                        {t.done ? <CheckCircle2 className="size-5 text-success" /> : <Circle className="size-5" />}
                      </button>
                    </TableCell>
                    <TableCell className={t.done ? 'text-muted-foreground line-through' : ''}>{t.title}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {t.campaign != null ? (campaignNames.get(t.campaign) ?? `#${t.campaign}`) : '—'}
                    </TableCell>
                    <TableCell>
                      {t.due_date ? (
                        <Badge variant={overdue ? 'destructive' : 'outline'}>
                          {overdue ? `Overdue · ${formatDate(t.due_date)}` : formatDate(t.due_date)}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
