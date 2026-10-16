import { cn } from '@/lib/utils';

interface EmptyStateProps {
  icon?: React.ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'enter flex flex-col items-center justify-center gap-2 rounded-card border border-dashed border-input bg-card/60 px-6 py-12 text-center',
        className,
      )}
    >
      {Icon && (
        <span className="mb-1 flex size-13 items-center justify-center rounded-full bg-sage text-primary">
          <Icon className="size-6" aria-hidden />
        </span>
      )}
      <p className="font-bold tracking-tight">{title}</p>
      {description && <p className="max-w-sm text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
