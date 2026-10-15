import { zodResolver } from '@hookform/resolvers/zod';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Pencil, Plus, ShoppingCart, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatCurrency, formatDateTime, dateTimeLocalToISO, toDateTimeLocalValue } from '@/lib/format';
import type { Campaign, OrderRef } from '@/lib/types';
import { Alert } from '@/ui/alert';
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

const orderSchema = z.object({
  external_id: z.string().trim().min(1, 'Order ID is required.'),
  campaign: z.string(),
  total: z.coerce.number().min(0, 'Must be 0 or more.'),
  ordered_at: z.string(),
});

type OrderValues = z.infer<typeof orderSchema>;

function OrderDialog({
  open,
  onOpenChange,
  order,
  campaigns,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  order: OrderRef | null;
  campaigns: Campaign[];
}) {
  const qc = useQueryClient();
  const form = useForm<z.input<typeof orderSchema>, unknown, z.output<typeof orderSchema>>({
    resolver: zodResolver(orderSchema),
    defaultValues: { external_id: '', campaign: '', total: 0, ordered_at: '' },
  });
  const { register, control, handleSubmit, reset, formState: { errors } } = form;

  useEffect(() => {
    if (open) {
      reset(
        order
          ? {
              external_id: order.external_id,
              campaign: order.campaign != null ? String(order.campaign) : '',
              total: Number(order.total),
              ordered_at: toDateTimeLocalValue(order.ordered_at),
            }
          : { external_id: '', campaign: '', total: 0, ordered_at: '' },
      );
    }
  }, [open, order, reset]);

  const save = useMutation({
    mutationFn: async (values: OrderValues) => {
      const payload = {
        external_id: values.external_id,
        campaign: values.campaign ? Number(values.campaign) : null,
        total: values.total,
        ordered_at: dateTimeLocalToISO(values.ordered_at),
      };
      return (order ? await api.patch<OrderRef>(`/orders/${order.id}/`, payload) : await api.post<OrderRef>('/orders/', payload)).data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['orders'] });
      toast.success(order ? 'Order updated' : 'Order added');
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{order ? 'Edit order' : 'New order'}</DialogTitle>
          <DialogDescription>
            Orders usually arrive from the shop. Link them to a campaign here to attribute revenue manually.
          </DialogDescription>
        </DialogHeader>
        {save.isError && (
          <Alert variant="destructive" className="mb-4">
            {getErrorMessage(save.error)}
          </Alert>
        )}
        <form id="order-form" noValidate onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Order ID" htmlFor="order-external" error={errors.external_id?.message}>
              <Input id="order-external" placeholder="WEB-1042" {...register('external_id')} />
            </Field>
            <Field label="Total (€)" htmlFor="order-total" error={errors.total?.message}>
              <Input id="order-total" type="number" step="0.01" {...register('total')} />
            </Field>
          </div>
          <Field label="Campaign" error={errors.campaign?.message}>
            <Controller
              control={control}
              name="campaign"
              render={({ field }) => (
                <Select value={field.value || 'none'} onValueChange={(v) => field.onChange(v === 'none' ? '' : v)}>
                  <SelectTrigger aria-label="Campaign">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Not attributed</SelectItem>
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
          <Field label="Ordered at" htmlFor="order-ordered" error={errors.ordered_at?.message} hint="Optional — defaults to now if left empty.">
            <Input id="order-ordered" type="datetime-local" {...register('ordered_at')} />
          </Field>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="order-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : order ? 'Save changes' : 'Add order'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function OrdersPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [campaignFilter, setCampaignFilter] = useState('all');
  const [ordering, setOrdering] = useState('-ordered_at');
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<OrderRef | null>(null);
  const [deleting, setDeleting] = useState<OrderRef | null>(null);

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
      campaign: campaignFilter === 'all' ? undefined : Number(campaignFilter),
      ordering,
    }),
    [page, campaignFilter, ordering],
  );

  const list = useQuery({
    queryKey: qk.orders(params),
    queryFn: () => fetchList<OrderRef>('/orders/', params),
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: async (order: OrderRef) => api.delete(`/orders/${order.id}/`),
    onSuccess: (_data, order) => {
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ['orders'] });
      toast.success(`Order ${order.external_id} deleted`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const rows = list.data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Orders"
        description="Shop orders with utm attribution, used to check campaign revenue against real sales."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus /> New order
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
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
          value={ordering}
          onValueChange={(v) => {
            setOrdering(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-44" aria-label="Sort orders">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="-ordered_at">Newest first</SelectItem>
            <SelectItem value="ordered_at">Oldest first</SelectItem>
            <SelectItem value="-total">Highest total</SelectItem>
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
          icon={ShoppingCart}
          title={campaignFilter !== 'all' ? 'No orders for this campaign' : 'No orders yet'}
          description={
            campaignFilter !== 'all'
              ? 'Clear the campaign filter to see every order.'
              : 'Orders synced from the shop appear here; you can also add them manually.'
          }
          action={
            campaignFilter !== 'all' ? (
              <Button variant="outline" onClick={() => setCampaignFilter('all')}>
                Clear filter
              </Button>
            ) : (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus /> New order
              </Button>
            )
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order</TableHead>
                <TableHead className="hidden sm:table-cell">Ordered</TableHead>
                <TableHead>Campaign</TableHead>
                <TableHead className="hidden lg:table-cell">Attribution</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((o) => (
                <TableRow key={o.id}>
                  <TableCell className="font-mono text-xs">{o.external_id}</TableCell>
                  <TableCell className="hidden text-muted-foreground sm:table-cell">{formatDateTime(o.ordered_at)}</TableCell>
                  <TableCell>
                    {o.campaign != null ? (
                      <Link to={`/campaigns/${o.campaign}`} className="text-primary hover:underline">
                        {campaignNames.get(o.campaign) ?? `#${o.campaign}`}
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">Unattributed</span>
                    )}
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {o.utm_source || o.utm_medium || o.utm_campaign ? (
                      <span className="text-xs text-muted-foreground">
                        {[o.utm_source, o.utm_medium, o.utm_campaign].filter(Boolean).join(' / ')}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(o.total)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label="Order actions">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditing(o)}>
                          <Pencil /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(o)}>
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

      <OrderDialog open={createOpen} onOpenChange={setCreateOpen} order={null} campaigns={campaigns.data?.results ?? []} />
      <OrderDialog
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        order={editing}
        campaigns={campaigns.data?.results ?? []}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete order?"
        description={deleting ? `Order ${deleting.external_id} will be removed permanently.` : undefined}
        confirmLabel="Delete"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  );
}
