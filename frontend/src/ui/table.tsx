import { cn } from '@/lib/utils';

export function Table({ className, ...props }: React.ComponentProps<'table'>) {
  return (
    <div className="overflow-hidden rounded-card border border-border bg-card shadow-soft">
      <div className="overflow-x-auto">
        <table className={cn('w-full caption-bottom text-sm', className)} {...props} />
      </div>
    </div>
  );
}

export function TableHeader({ className, ...props }: React.ComponentProps<'thead'>) {
  return <thead className={cn('bg-surface-alt', className)} {...props} />;
}

export function TableBody({ className, ...props }: React.ComponentProps<'tbody'>) {
  return <tbody className={cn('[&_tr:last-child]:border-0', className)} {...props} />;
}

export function TableRow({ className, ...props }: React.ComponentProps<'tr'>) {
  return <tr className={cn('border-b border-border/70 transition-colors hover:bg-muted/50', className)} {...props} />;
}

export function TableHead({ className, ...props }: React.ComponentProps<'th'>) {
  return (
    <th
      className={cn('h-11 px-4 text-left align-middle text-xs font-bold tracking-wider text-muted-foreground uppercase', className)}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: React.ComponentProps<'td'>) {
  return <td className={cn('px-4 py-3 align-middle', className)} {...props} />;
}
