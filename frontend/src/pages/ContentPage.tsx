import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, FileText, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { ContentItemDialog } from '@/components/ContentItemDialog';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import type { Campaign, Channel, ContentItem } from '@/lib/types';
import { Button } from '@/ui/button';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/ui/dropdown-menu';
import { EmptyState } from '@/ui/empty-state';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { ContentStatusBadge } from '@/ui/status-badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const PAGE_SIZE = 20;

export default function ContentPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ContentItem | null>(null);
  const [deleting, setDeleting] = useState<ContentItem | null>(null);

  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 200 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 200, ordering: 'name' }),
  });
  const channels = useQuery({
    queryKey: qk.channels({ page_size: 200 }),
    queryFn: () => fetchList<Channel>('/channels/', { page_size: 200, ordering: 'name' }),
  });
  const campaignNames = useMemo(
    () => new Map((campaigns.data?.results ?? []).map((c) => [c.id, c.name])),
    [campaigns.data],
  );
  const channelNames = useMemo(
    () => new Map((channels.data?.results ?? []).map((c) => [c.id, c.name])),
    [channels.data],
  );

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      ordering: '-publish_at',
      search: search.trim() || undefined,
      campaign: campaignFilter === 'all' ? undefined : Number(campaignFilter),
      status: statusFilter === 'all' ? undefined : statusFilter,
    }),
    [page, search, campaignFilter, statusFilter],
  );

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
  const hasFilters = Boolean(search.trim()) || campaignFilter !== 'all' || statusFilter !== 'all';

  return (
    <div>
      <PageHeader
        title="Content"
        description="Everything planned and published across campaigns."
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setDialogOpen(true);
            }}
          >
            <Plus /> New content
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="pl-9"
            placeholder="Search title or copy…"
            aria-label="Search content"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
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
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="draft">Draft</SelectItem>
            <SelectItem value="scheduled">Scheduled</SelectItem>
            <SelectItem value="published">Published</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {list.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={FileText}
          title={hasFilters ? 'No content matches your filters' : 'No content yet'}
          description={
            hasFilters
              ? 'Try clearing a filter or searching something else.'
              : 'Plan your first post, story or ad — schedule it and watch the calendar fill up.'
          }
          action={
            hasFilters ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSearch('');
                  setCampaignFilter('all');
                  setStatusFilter('all');
                }}
              >
                Clear filters
              </Button>
            ) : (
              <Button
                onClick={() => {
                  setEditing(null);
                  setDialogOpen(true);
                }}
              >
                <Plus /> New content
              </Button>
            )
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Title</TableHead>
                <TableHead>Campaign</TableHead>
                <TableHead className="hidden md:table-cell">Channel</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="hidden lg:table-cell">Publish at</TableHead>
                <TableHead className="w-24" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="max-w-70">
                    <span className="font-medium">{item.title}</span>
                    {item.link && (
                      <a
                        href={item.link}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-2 inline-flex align-middle text-muted-foreground hover:text-primary"
                        aria-label="Open link"
                      >
                        <ExternalLink className="size-3.5" />
                      </a>
                    )}
                    {item.copy && <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.copy}</p>}
                  </TableCell>
                  <TableCell>
                    <Link to={`/campaigns/${item.campaign}`} className="text-primary hover:underline">
                      {campaignNames.get(item.campaign) ?? `#${item.campaign}`}
                    </Link>
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground md:table-cell">
                    {item.channel != null ? (channelNames.get(item.channel) ?? `#${item.channel}`) : '—'}
                  </TableCell>
                  <TableCell>
                    <ContentStatusBadge status={item.status} />
                  </TableCell>
                  <TableCell className="hidden text-muted-foreground lg:table-cell">
                    {formatDateTime(item.publish_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label="Content actions">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onSelect={() => {
                            setEditing(item);
                            setDialogOpen(true);
                          }}
                        >
                          <Pencil /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(item)}>
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

      <ContentItemDialog
        open={dialogOpen}
        onOpenChange={(open) => {
          setDialogOpen(open);
          if (!open) setEditing(null);
        }}
        item={editing}
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
