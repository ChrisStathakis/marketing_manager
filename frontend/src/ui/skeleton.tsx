import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export function Skeleton({ className, ...props }: React.ComponentProps<'div'>) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-field bg-[linear-gradient(90deg,var(--muted)_0%,var(--surface-alt)_50%,var(--muted)_100%)]',
        className,
      )}
      {...props}
    />
  );
}

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-label={label ?? 'Loading'} className={cn('inline-flex items-center gap-2 text-sm text-muted-foreground', className)}>
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}
    </span>
  );
}
