import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-semibold transition-all duration-150 active:scale-[0.97] disabled:pointer-events-none disabled:opacity-55 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: 'bg-primary-solid text-primary-foreground shadow-soft hover:bg-primary-solid-hover',
        secondary: 'border-[1.5px] border-border bg-card text-primary shadow-soft hover:border-input hover:bg-sage',
        outline: 'border border-border bg-card shadow-soft hover:bg-muted',
        ghost: 'text-primary hover:bg-sage',
        destructive: 'bg-destructive text-destructive-foreground shadow-soft hover:bg-destructive/90',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9.5 px-4.5 py-2',
        sm: 'h-8 rounded-full px-3.5 text-xs',
        lg: 'h-11 px-6',
        icon: 'size-9.5',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
);

export type ButtonProps = React.ComponentProps<'button'> & VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, type = 'button', ...props }: ButtonProps) {
  return <button type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
