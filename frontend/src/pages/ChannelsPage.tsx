import { zodResolver } from '@hookform/resolvers/zod';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pause, Pencil, Play, Plus, Radio, Search, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import type { Channel } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Badge } from '@/ui/badge';
import { Button } from '@/ui/button';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/ui/dropdown-menu';
import { EmptyState } from '@/ui/empty-state';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const PAGE_SIZE = 20;

const CHANNEL_TYPES = [
  { value: 'facebook', label: 'Facebook' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'google', label: 'Google' },
  { value: 'x', label: 'X' },
  { value: 'other', label: 'Other' },
] as const;

const typeLabel = (value: string) => CHANNEL_TYPES.find((t) => t.value === value)?.label ?? value;

const channelSchema = z.object({
  name: z.string().trim().min(1, 'Name is required.'),
  channel_type: z.string().min(1, 'Pick a type.'),
  handle: z.string(),
});

type ChannelValues = z.infer<typeof channelSchema>;

function ChannelDialog({
  open,
  onOpenChange,
  channel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  channel: Channel | null;
}) {
  const qc = useQueryClient();
  const form = useForm<ChannelValues>({
    resolver: zodResolver(channelSchema),
    defaultValues: { name: '', channel_type: 'other', handle: '' },
  });
  const { register, control, handleSubmit, reset, formState: { errors } } = form;

  useEffect(() => {
    if (open) {
      reset(
        channel
          ? { name: channel.name, channel_type: channel.channel_type, handle: channel.handle }
          : { name: '', channel_type: 'other', handle: '' },
      );
    }
  }, [open, channel, reset]);

  const save = useMutation({
    mutationFn: async (values: ChannelValues) =>
      (channel ? await api.patch<Channel>(`/channels/${channel.id}/`, values) : await api.post<Channel>('/channels/', values)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channels'] });
      toast.success(channel ? 'Channel updated' : 'Channel added');
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{channel ? 'Edit channel' : 'New channel'}</DialogTitle>
          <DialogDescription>
            Channels group ad spend: for example your Instagram profile or a Google Ads account.
          </DialogDescription>
        </DialogHeader>
        {save.isError && (
          <Alert variant="destructive" className="mb-4">
            {getErrorMessage(save.error)}
          </Alert>
        )}
        <form id="channel-form" noValidate onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
          <Field label="Name" htmlFor="channel-name" error={errors.name?.message}>
            <Input id="channel-name" placeholder="Main Instagram" {...register('name')} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Type" error={errors.channel_type?.message}>
              <Controller
                control={control}
                name="channel_type"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="Channel type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CHANNEL_TYPES.map((t) => (
                        <SelectItem key={t.value} value={t.value}>
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Handle" htmlFor="channel-handle" error={errors.handle?.message} hint="Optional, e.g. @basket.co">
              <Input id="channel-handle" placeholder="@basket.co" {...register('handle')} />
            </Field>
          </div>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="channel-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : channel ? 'Save changes' : 'Add channel'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ChannelsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [type, setType] = useState('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Channel | null>(null);
  const [deleting, setDeleting] = useState<Channel | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch || undefined,
      channel_type: type === 'all' ? undefined : type,
      ordering: 'name',
    }),
    [page, debouncedSearch, type],
  );

  const list = useQuery({
    queryKey: qk.channels(params),
    queryFn: () => fetchList<Channel>('/channels/', params),
    placeholderData: keepPreviousData,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['channels'] });
  };

  const toggleActive = useMutation({
    mutationFn: async (channel: Channel) => (await api.patch(`/channels/${channel.id}/`, { is_active: !channel.is_active })).data,
    onSuccess: (_data, channel) => {
      invalidate();
      toast.success(`"${channel.name}" ${channel.is_active ? 'deactivated' : 'activated'}`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: async (channel: Channel) => api.delete(`/channels/${channel.id}/`),
    onSuccess: (_data, channel) => {
      setDeleting(null);
      invalidate();
      toast.success(`"${channel.name}" deleted`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const rows = list.data?.results ?? [];
  const hasFilters = Boolean(debouncedSearch) || type !== 'all';

  return (
    <div>
      <PageHeader
        title="Channels"
        description="Where your campaigns run — used to tag ad spend by channel."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus /> New channel
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="pl-9"
            placeholder="Search channels…"
            aria-label="Search channels"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <Select
          value={type}
          onValueChange={(v) => {
            setType(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by type">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {CHANNEL_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {list.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10" />
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Radio}
          title={hasFilters ? 'No channels match your filters' : 'No channels yet'}
          description={
            hasFilters
              ? 'Try a different search term or clear the type filter.'
              : 'Add the profiles and ad accounts you spend on.'
          }
          action={
            hasFilters ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch('');
                  setType('all');
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus /> New channel
              </Button>
            )
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Channel</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden md:table-cell">Handle</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.id}>
                  <TableCell className="font-medium">{c.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{typeLabel(c.channel_type)}</Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={c.is_active ? 'success' : 'outline'}>{c.is_active ? 'Active' : 'Inactive'}</Badge>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">{c.handle || '—'}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label="Channel actions">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditing(c)}>
                          <Pencil /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => toggleActive.mutate(c)}>
                          {c.is_active ? (
                            <>
                              <Pause /> Deactivate
                            </>
                          ) : (
                            <>
                              <Play /> Activate
                            </>
                          )}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(c)}>
                          <Trash2 /> Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}

      <ChannelDialog open={createOpen} onOpenChange={setCreateOpen} channel={null} />
      <ChannelDialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)} channel={editing} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete channel?"
        description={
          deleting
            ? `"${deleting.name}" will be removed. Existing spend rows keep their numbers but lose the channel label.`
            : undefined
        }
        confirmLabel="Delete"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  );
}
