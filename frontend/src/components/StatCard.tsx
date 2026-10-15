import { TrendingDown, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  hint?: string;
  /** Percent change vs the previous period; null/undefined hides the badge. */
  delta?: number | null;
  className?: string;
}

export function StatCard({ label, value, icon: Icon, hint, delta, className }: StatCardProps) {
  return (
    <div className={cn('flex items-start gap-3 rounded-xl border border-border bg-card p-4 shadow-xs', className)}>
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="size-4.5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        <p className="mt-0.5 text-xl font-semibold tracking-tight tabular-nums">{value}</p>
        {delta != null && (
          <p
            className={cn(
              'mt-0.5 inline-flex items-center gap-1 text-xs font-medium tabular-nums',
              delta >= 0 ? 'text-success' : 'text-destructive',
            )}
          >
            {delta >= 0 ? <TrendingUp className="size-3" aria-hidden /> : <TrendingDown className="size-3" aria-hidden />}
            {delta > 0 ? '+' : ''}
            {delta.toFixed(1)}%
            <span className="font-normal text-muted-foreground">vs previous period</span>
          </p>
        )}
        {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
      </div>
    </div>
  );
}
