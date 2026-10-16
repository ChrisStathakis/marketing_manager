import { cn } from '@/lib/utils';

export function Label({ className, ...props }: React.ComponentProps<'label'>) {
  return <label className={cn('text-[0.8125rem] font-semibold tracking-[0.01em] text-ink-soft', className)} {...props} />;
}
