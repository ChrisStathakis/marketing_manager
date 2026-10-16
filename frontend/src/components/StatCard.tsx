import { TrendingDown, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  hint?: string;
  /** Percent change vs the previous period; null/undefined hides the badge. */
  delta?: number | null;
  /** Pine-filled emphasis card (the reference app's featured stat). */
  featured?: boolean;
  className?: string;
}

export function StatCard({ label, value, icon: Icon, hint, delta, featured = false, className }: StatCardProps) {
  return (
    <div
      className={cn(
        'flex items-start gap-3.5 rounded-card border p-4.5 shadow-soft',
        featured ? 'border-transparent bg-primary-solid text-primary-foreground' : 'border-border bg-card',
        className,
      )}
    >
      <span
        className={cn(
          'flex size-9.5 shrink-0 items-center justify-center rounded-full',
          featured ? 'bg-white/15 text-primary-foreground' : 'bg-sage text-primary',
        )}
      >
        <Icon className="size-4.5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className={cn('text-[0.65rem] font-bold tracking-[0.16em] uppercase', featured ? 'text-primary-foreground/75' : 'text-muted-foreground')}>
          {label}
        </p>
        <p className="mt-1 text-xl leading-tight font-bold tracking-tight tabular-nums">{value}</p>
        {delta != null && (
          <p
            className={cn(
              'mt-1 inline-flex items-center gap-1 text-xs font-semibold tabular-nums',
              featured
                ? delta >= 0
                  ? 'text-lime'
                  : 'text-[#f0b5a3]'
                : delta >= 0
                  ? 'text-success'
                  : 'text-destructive',
            )}
          >
            {delta >= 0 ? <TrendingUp className="size-3" aria-hidden /> : <TrendingDown className="size-3" aria-hidden />}
            {delta > 0 ? '+' : ''}
            {delta.toFixed(1)}%
            <span className={cn('font-normal', featured ? 'text-primary-foreground/70' : 'text-muted-foreground')}>
              vs previous period
            </span>
          </p>
        )}
        {hint && <p className={cn('mt-0.5 text-xs', featured ? 'text-primary-foreground/70' : 'text-muted-foreground')}>{hint}</p>}
      </div>
    </div>
  );
}
