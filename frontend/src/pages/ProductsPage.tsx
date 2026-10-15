import { zodResolver } from '@hookform/resolvers/zod';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, Package, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatCurrency, formatDateTime } from '@/lib/format';
import type { Product } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/ui/dropdown-menu';
import { EmptyState } from '@/ui/empty-state';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Pagination } from '@/ui/pagination';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const PAGE_SIZE = 20;

const productSchema = z.object({
  external_id: z.string().trim().min(1, 'Shop ID is required.'),
  name: z.string().trim().min(1, 'Name is required.'),
  price: z.coerce.number().min(0, 'Must be 0 or more.'),
  url: z
    .string()
    .refine((v) => v === '' || /^https?:\/\/\S+$/i.test(v), 'Enter a full URL (https://…) or leave empty.'),
});

type ProductValues = z.infer<typeof productSchema>;

function ProductDialog({
  open,
  onOpenChange,
  product,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: Product | null;
}) {
  const qc = useQueryClient();
  const form = useForm<z.input<typeof productSchema>, unknown, z.output<typeof productSchema>>({
    resolver: zodResolver(productSchema),
    defaultValues: { external_id: '', name: '', price: 0, url: '' },
  });
  const { register, handleSubmit, reset, formState: { errors } } = form;

  useEffect(() => {
    if (open) {
      reset(
        product
          ? { external_id: product.external_id, name: product.name, price: Number(product.price), url: product.url }
          : { external_id: '', name: '', price: 0, url: '' },
      );
    }
  }, [open, product, reset]);

  const save = useMutation({
    mutationFn: async (values: ProductValues) =>
      (
        product
          ? await api.patch<Product>(`/products/${product.id}/`, values)
          : await api.post<Product>('/products/', values)
      ).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['products'] });
      toast.success(product ? 'Product updated' : 'Product added');
      onOpenChange(false);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{product ? 'Edit product' : 'New product'}</DialogTitle>
          <DialogDescription>
            Baskets you promote. The shop ID should match the identifier in your store exports.
          </DialogDescription>
        </DialogHeader>
        {save.isError && (
          <Alert variant="destructive" className="mb-4">
            {getErrorMessage(save.error)}
          </Alert>
        )}
        <form id="product-form" noValidate onSubmit={handleSubmit((v) => save.mutate(v))} className="grid gap-4">
          <Field label="Name" htmlFor="product-name" error={errors.name?.message}>
            <Input id="product-name" placeholder="Easter basket — large" {...register('name')} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Shop ID" htmlFor="product-external" error={errors.external_id?.message}>
              <Input id="product-external" placeholder="SKU-123" {...register('external_id')} />
            </Field>
            <Field label="Price (€)" htmlFor="product-price" error={errors.price?.message}>
              <Input id="product-price" type="number" step="0.01" {...register('price')} />
            </Field>
          </div>
          <Field label="Product URL" htmlFor="product-url" error={errors.url?.message} hint="Optional link to the product page.">
            <Input id="product-url" placeholder="https://shop.example.com/easter-basket" {...register('url')} />
          </Field>
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="product-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : product ? 'Save changes' : 'Add product'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function ProductsPage() {
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<Product | null>(null);
  const [deleting, setDeleting] = useState<Product | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      search: debouncedSearch || undefined,
      ordering: 'name',
    }),
    [page, debouncedSearch],
  );

  const list = useQuery({
    queryKey: qk.products(params),
    queryFn: () => fetchList<Product>('/products/', params),
    placeholderData: keepPreviousData,
  });

  const remove = useMutation({
    mutationFn: async (product: Product) => api.delete(`/products/${product.id}/`),
    onSuccess: (_data, product) => {
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ['products'] });
      toast.success(`"${product.name}" deleted`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const rows = list.data?.results ?? [];

  return (
    <div>
      <PageHeader
        title="Products"
        description="The baskets you promote, referenced by order items and campaigns."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus /> New product
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="pl-9"
            placeholder="Search products…"
            aria-label="Search products"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
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
          icon={Package}
          title={debouncedSearch ? 'No products match your search' : 'No products yet'}
          description={
            debouncedSearch
              ? 'Try a different term.'
              : 'Add the baskets you sell so results and orders can reference them.'
          }
          action={
            debouncedSearch ? (
              <Button variant="outline" onClick={() => setSearch('')}>
                Clear search
              </Button>
            ) : (
              <Button onClick={() => setCreateOpen(true)}>
                <Plus /> New product
              </Button>
            )
          }
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead className="hidden sm:table-cell">Shop ID</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="hidden lg:table-cell">Updated</TableHead>
                <TableHead className="w-12" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="max-w-70">
                    <span className="font-medium">{p.name}</span>
                    {p.url && (
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="size-3" aria-hidden /> Open product page
                      </a>
                    )}
                  </TableCell>
                  <TableCell className="hidden font-mono text-xs text-muted-foreground sm:table-cell">{p.external_id}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatCurrency(p.price)}</TableCell>
                  <TableCell className="hidden text-muted-foreground lg:table-cell">{formatDateTime(p.updated_at)}</TableCell>
                  <TableCell className="text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" aria-label="Product actions">
                          ⋯
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onSelect={() => setEditing(p)}>
                          <Pencil /> Edit
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem className="text-destructive" onSelect={() => setDeleting(p)}>
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

      <ProductDialog open={createOpen} onOpenChange={setCreateOpen} product={null} />
      <ProductDialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)} product={editing} />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete product?"
        description={deleting ? `"${deleting.name}" will be removed from the catalog.` : undefined}
        confirmLabel="Delete"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  );
}
