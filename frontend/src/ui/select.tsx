import * as SelectPrimitive from '@radix-ui/react-select';
import { Check, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;
export const SelectGroup = SelectPrimitive.Group;

export function SelectTrigger({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Trigger>) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        'flex h-9.5 w-full items-center justify-between gap-2 rounded-field border-[1.5px] border-input bg-card px-3.5 py-2 text-sm text-foreground shadow-xs transition-[color,background-color,border-color,box-shadow] duration-150',
        'hover:border-moss/60 data-[placeholder]:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50 [&>span]:truncate',
        'focus-visible:border-moss focus-visible:ring-4 focus-visible:ring-ring/20 focus-visible:outline-none',
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  position = 'popper',
  ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position={position}
        className={cn(
          'relative z-50 max-h-80 min-w-32 overflow-hidden rounded-field border border-border bg-card text-foreground shadow-lift data-[state=open]:animate-pop',
          position === 'popper' && 'w-(--radix-select-trigger-width)',
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectItem({ className, children, ...props }: React.ComponentProps<typeof SelectPrimitive.Item>) {
  return (
    <SelectPrimitive.Item
      className={cn(
        'relative flex cursor-default select-none items-center rounded-[9px] py-1.5 pr-8 pl-2.5 text-sm font-medium outline-none',
        'data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-highlighted:bg-sage',
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-2.5 flex items-center">
        <Check className="size-4 text-primary" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}
