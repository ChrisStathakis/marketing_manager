import { cn } from '@/lib/utils';

export function Input({ className, ...props }: React.ComponentProps<'input'>) {
  return (
    <input
      className={cn(
        'flex h-9.5 w-full rounded-field border-[1.5px] border-input bg-card px-3.5 py-1 text-sm text-foreground shadow-xs transition-[color,background-color,border-color,box-shadow] duration-150',
        'placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50',
        'focus-visible:border-moss focus-visible:ring-4 focus-visible:ring-ring/20 focus-visible:outline-none',
        'file:mr-3 file:h-7 file:rounded-full file:border-0 file:bg-muted file:px-2.5 file:text-xs file:font-medium file:text-foreground',
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: React.ComponentProps<'textarea'>) {
  return (
    <textarea
      className={cn(
        'flex min-h-20 w-full rounded-field border-[1.5px] border-input bg-card px-3.5 py-2 text-sm text-foreground shadow-xs transition-[color,background-color,border-color,box-shadow] duration-150',
        'placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50',
        'focus-visible:border-moss focus-visible:ring-4 focus-visible:ring-ring/20 focus-visible:outline-none',
        className,
      )}
      {...props}
    />
  );
}
