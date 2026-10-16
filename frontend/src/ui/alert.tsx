import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

const VARIANTS = {
  info: { icon: Info, className: 'border-moss/25 bg-sage text-foreground' },
  success: { icon: CheckCircle2, className: 'border-success/30 bg-success-soft text-foreground' },
  destructive: { icon: AlertTriangle, className: 'border-destructive/30 bg-destructive-soft text-foreground' },
} as const;

export function Alert({
  variant = 'info',
  title,
  children,
  className,
}: {
  variant?: keyof typeof VARIANTS;
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const { icon: Icon, className: variantClass } = VARIANTS[variant];
  return (
    <div role={variant === 'destructive' ? 'alert' : 'status'} className={cn('flex gap-3 rounded-field border p-3.5 text-sm', variantClass, className)}>
      <Icon className={cn('mt-0.5 size-4 shrink-0', variant === 'destructive' && 'text-destructive', variant === 'success' && 'text-success', variant === 'info' && 'text-primary')} aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="text-muted-foreground">{children}</div>}
      </div>
    </div>
  );
}
