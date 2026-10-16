import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarDays,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  FileText,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';
import { ContentItemDialog } from '@/components/ContentItemDialog';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatDate, toDateInputValue } from '@/lib/format';
import type { Campaign, ContentItem, Task } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Button } from '@/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { ContentStatusBadge } from '@/ui/status-badge';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const TODAY_KEY = toDateInputValue(new Date());

function startOfMonth(d: Date) {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function addMonths(d: Date, n: number) {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

interface DayItems {
  tasks: Task[];
  content: ContentItem[];
}

export default function CalendarPage() {
  const [month, setMonth] = useState(() => startOfMonth(new Date()));
  const [dayOpen, setDayOpen] = useState<string | null>(null);
  const [contentDialog, setContentDialog] = useState<{ open: boolean; item: ContentItem | null; date?: string }>({
    open: false,
    item: null,
  });

  const monthLastDay = useMemo(
    () => new Date(month.getFullYear(), month.getMonth() + 1, 0),
    [month],
  );

  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 200 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 200, ordering: 'name' }),
  });
  const campaignNames = useMemo(
    () => new Map((campaigns.data?.results ?? []).map((c) => [c.id, c.name])),
    [campaigns.data],
  );

  const tasks = useQuery({
    queryKey: qk.tasks({ month: toDateInputValue(month) }),
    queryFn: () =>
      fetchList<Task>('/tasks/', {
        page_size: 200,
        ordering: 'due_date',
        due_date__gte: toDateInputValue(month),
        due_date__lte: toDateInputValue(monthLastDay),
      }),
  });

  const content = useQuery({
    queryKey: qk.content({ month: toDateInputValue(month) }),
    queryFn: () =>
      fetchList<ContentItem>('/content/', {
        page_size: 200,
        ordering: 'publish_at',
        publish_at__gte: month.toISOString(),
        publish_at__lte: new Date(monthLastDay.getTime() + 86_399_999).toISOString(),
      }),
  });

  const byDay = useMemo(() => {
    const map = new Map<string, DayItems>();
    const get = (key: string): DayItems => {
      let entry = map.get(key);
      if (!entry) {
        entry = { tasks: [], content: [] };
        map.set(key, entry);
      }
      return entry;
    };
    for (const task of tasks.data?.results ?? []) {
      if (task.due_date) get(task.due_date).tasks.push(task);
    }
    for (const item of content.data?.results ?? []) {
      if (item.publish_at) get(toDateInputValue(new Date(item.publish_at))).content.push(item);
    }
    return map;
  }, [tasks.data, content.data]);

  const weeks = useMemo(() => {
    const first = startOfMonth(month);
    const offset = (first.getDay() + 6) % 7; // Monday-based index
    const gridStart = new Date(first);
    gridStart.setDate(first.getDate() - offset);
    const total = offset + monthLastDay.getDate();
    const weekCount = Math.ceil(total / 7);
    return Array.from({ length: weekCount }, (_, w) =>
      Array.from({ length: 7 }, (_, d) => {
        const day = new Date(gridStart);
        day.setDate(gridStart.getDate() + w * 7 + d);
        return day;
      }),
    );
  }, [month, monthLastDay]);

  const isLoading = tasks.isLoading || content.isLoading;
  const monthLabel = month.toLocaleDateString('en-IE', { month: 'long', year: 'numeric' });

  const agenda = [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b));

  return (
    <div>
      <PageHeader
        title="Calendar"
        description="Tasks and scheduled content for the month."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => {
                setContentDialog({ open: true, item: null });
              }}
            >
              <FileText /> New content
            </Button>
          </>
        }
      />

      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" aria-label="Previous month" onClick={() => setMonth(addMonths(month, -1))}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setMonth(startOfMonth(new Date()))}>
            Today
          </Button>
          <Button variant="outline" size="icon" aria-label="Next month" onClick={() => setMonth(addMonths(month, 1))}>
            <ChevronRight />
          </Button>
        </div>
        <h2 className="text-lg font-semibold tracking-tight">{monthLabel}</h2>
        <div className="hidden items-center gap-3 text-xs text-muted-foreground sm:flex">
          <span className="flex items-center gap-1">
            <Circle className="size-3" /> Task
          </span>
          <span className="flex items-center gap-1">
            <FileText className="size-3" /> Content
          </span>
        </div>
      </div>

      {/* Desktop month grid */}
      <div className="hidden overflow-hidden rounded-card border border-border bg-card shadow-soft md:block">
        <div className="grid grid-cols-7 border-b border-border bg-muted/60">
          {WEEKDAYS.map((d) => (
            <div key={d} className="px-2 py-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {d}
            </div>
          ))}
        </div>
        {isLoading ? (
          <div className="flex h-96 items-center justify-center text-sm text-muted-foreground">Loading…</div>
        ) : (
          weeks.map((week, wi) => (
            <div key={wi} className="grid grid-cols-7 border-b border-border last:border-b-0">
              {week.map((day) => {
                const key = toDateInputValue(day);
                const inMonth = day.getMonth() === month.getMonth();
                const items = byDay.get(key);
                const isToday = key === TODAY_KEY;
                return (
                  <div
                    key={key}
                    role="button"
                    tabIndex={0}
                    onClick={() => setDayOpen(key)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setDayOpen(key);
                      }
                    }}
                    className={cn(
                      'min-h-28 cursor-pointer border-r border-border p-1.5 transition-colors last:border-r-0 hover:bg-muted/40',
                      !inMonth && 'bg-muted/30 text-muted-foreground',
                      isToday && 'bg-primary/5',
                    )}
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <span className={cn('text-xs tabular-nums', isToday && 'font-semibold text-primary')}>
                        {day.getDate()}
                      </span>
                      {items && items.tasks.length + items.content.length > 3 && (
                        <span className="text-[10px] text-muted-foreground">
                          +{items.tasks.length + items.content.length - 3}
                        </span>
                      )}
                    </div>
                    <div className="space-y-1">
                      {items?.tasks.slice(0, 2).map((task) => (
                        <Chip
                          key={`t${task.id}`}
                          icon={task.done ? CheckCircle2 : Circle}
                          label={task.title}
                          className={cn(
                            task.done && 'text-muted-foreground line-through',
                            !task.done && task.due_date! < TODAY_KEY && 'border-destructive/40 text-destructive',
                          )}
                        />
                      ))}
                      {items?.content.slice(0, 3).map((item) => (
                        <Chip
                          key={`c${item.id}`}
                          icon={FileText}
                          label={item.title}
                          className={cn(
                            item.status === 'published' && 'border-success/40 text-success',
                            item.status === 'scheduled' && 'border-warning/50 text-warning-foreground dark:text-warning',
                          )}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>

      {/* Mobile agenda */}
      <div className="space-y-3 md:hidden">
        {agenda.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing planned this month yet.</p>
        ) : (
          agenda.map(([key, items]) => (
            <div key={key} className="rounded-card border border-border bg-card p-3">
              <p className={cn('mb-2 text-sm font-medium', key === TODAY_KEY && 'text-primary')}>
                {formatDate(key)}
                {key === TODAY_KEY && ' · Today'}
              </p>
              <ul className="space-y-1.5">
                {items.tasks.map((task) => (
                  <li key={`t${task.id}`} className="flex items-center gap-2 text-sm">
                    {task.done ? <CheckCircle2 className="size-4 text-success" /> : <Circle className="size-4 text-muted-foreground" />}
                    <span className={task.done ? 'text-muted-foreground line-through' : ''}>{task.title}</span>
                  </li>
                ))}
                {items.content.map((item) => (
                  <li key={`c${item.id}`} className="flex items-center gap-2 text-sm">
                    <FileText className="size-4 text-muted-foreground" />
                    <span className="flex-1 truncate">{item.title}</span>
                    <ContentStatusBadge status={item.status} />
                  </li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      <DayDialog
        dateKey={dayOpen}
        onClose={() => setDayOpen(null)}
        items={dayOpen ? (byDay.get(dayOpen) ?? { tasks: [], content: [] }) : { tasks: [], content: [] }}
        campaignNames={campaignNames}
        campaigns={campaigns.data?.results ?? []}
        onNewContent={(date) => {
          setDayOpen(null);
          setContentDialog({ open: true, item: null, date });
        }}
        onEditContent={(item) => {
          setDayOpen(null);
          setContentDialog({ open: true, item });
        }}
      />

      <ContentItemDialog
        open={contentDialog.open}
        onOpenChange={(open) => setContentDialog((s) => ({ ...s, open }))}
        item={contentDialog.item}
        defaultDate={contentDialog.date}
      />
    </div>
  );
}

function Chip({
  icon: Icon,
  label,
  className,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        'flex items-center gap-1 truncate rounded-md border border-border bg-card px-1.5 py-0.5 text-[11px] leading-tight',
        className,
      )}
      title={label}
    >
      <Icon className="size-3 shrink-0" />
      <span className="truncate">{label}</span>
    </span>
  );
}

function DayDialog({
  dateKey,
  onClose,
  items,
  campaignNames,
  campaigns,
  onNewContent,
  onEditContent,
}: {
  dateKey: string | null;
  onClose: () => void;
  items: DayItems;
  campaignNames: Map<number, string>;
  campaigns: Campaign[];
  onNewContent: (date: string) => void;
  onEditContent: (item: ContentItem) => void;
}) {
  const qc = useQueryClient();
  const [title, setTitle] = useState('');
  const [campaign, setCampaign] = useState('none');
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['tasks'] });
    qc.invalidateQueries({ queryKey: ['content'] });
  };

  const addTask = useMutation({
    mutationFn: async () =>
      api.post('/tasks/', {
        title: title.trim(),
        due_date: dateKey,
        campaign: campaign === 'none' ? null : Number(campaign),
      }),
    onSuccess: () => {
      setTitle('');
      invalidate();
      toast.success('Task added');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const toggleTask = useMutation({
    mutationFn: async (task: Task) => api.patch(`/tasks/${task.id}/`, { done: !task.done }),
    onSuccess: invalidate,
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteTask = useMutation({
    mutationFn: async (task: Task) => api.delete(`/tasks/${task.id}/`),
    onSuccess: invalidate,
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const deleteContent = useMutation({
    mutationFn: async (item: ContentItem) => api.delete(`/content/${item.id}/`),
    onSuccess: () => {
      invalidate();
      toast.success('Content item deleted');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Dialog open={dateKey !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarDays className="size-4 text-primary" />
            {dateKey ? formatDate(dateKey) : ''}
          </DialogTitle>
          <DialogDescription>Tasks and content scheduled for this day.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (title.trim()) addTask.mutate();
            }}
          >
            <div className="min-w-40 flex-1">
              <Field label="Quick task" htmlFor="day-task-title">
                <Input
                  id="day-task-title"
                  placeholder="e.g. Reply to comments"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </Field>
            </div>
            <div className="w-40">
              <Field label="Campaign" htmlFor="day-task-campaign">
                <Select value={campaign} onValueChange={setCampaign}>
                  <SelectTrigger id="day-task-campaign" aria-label="Campaign">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {campaigns.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
            <Button type="submit" disabled={!title.trim() || addTask.isPending}>
              <Plus /> Add
            </Button>
          </form>

          <div>
            {items.tasks.length + items.content.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">Nothing planned yet for this day.</p>
            ) : (
              <ul className="space-y-2">
                {items.tasks.map((task) => (
                  <li key={`t${task.id}`} className="flex items-center gap-2 rounded-field border border-border px-3 py-2">
                    <button
                      className="text-muted-foreground transition-colors hover:text-primary"
                      aria-label={task.done ? 'Mark as not done' : 'Mark as done'}
                      onClick={() => toggleTask.mutate(task)}
                    >
                      {task.done ? <CheckCircle2 className="size-5 text-success" /> : <Circle className="size-5" />}
                    </button>
                    <span className={cn('flex-1 text-sm', task.done && 'text-muted-foreground line-through')}>{task.title}</span>
                    {task.campaign != null && (
                      <span className="text-xs text-muted-foreground">{campaignNames.get(task.campaign) ?? ''}</span>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete task"
                      onClick={() => deleteTask.mutate(task)}
                    >
                      <Trash2 />
                    </Button>
                  </li>
                ))}
                {items.content.map((item) => (
                  <li key={`c${item.id}`} className="flex items-center gap-2 rounded-field border border-border px-3 py-2">
                    <FileText className="size-4 shrink-0 text-muted-foreground" />
                    <span className="flex-1 truncate text-sm">{item.title}</span>
                    <ContentStatusBadge status={item.status} />
                    <Button variant="ghost" size="icon" aria-label="Edit content" onClick={() => onEditContent(item)}>
                      <Pencil />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Delete content"
                      onClick={() => deleteContent.mutate(item)}
                    >
                      <Trash2 />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button onClick={() => dateKey && onNewContent(dateKey)}>
            <Plus /> Content item
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
