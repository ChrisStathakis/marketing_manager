import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold tracking-wide whitespace-nowrap',
  {
    variants: {
      variant: {
        default: 'border-transparent bg-primary/12 text-primary',
        secondary: 'border-transparent bg-neutral-soft text-ink-soft',
        outline: 'border-border text-ink-soft',
        success: 'border-transparent bg-success-soft text-success',
        warning: 'border-transparent bg-warning-soft text-warning-foreground',
        destructive: 'border-transparent bg-destructive-soft text-destructive',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>['variant']>;

export function Badge({ className, variant, ...props }: React.ComponentProps<'span'> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
