import { useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import {
  CalendarDays,
  FileText,
  LayoutDashboard,
  Lightbulb,
  LogOut,
  Megaphone,
  Menu,
  Package,
  Radio,
  Settings,
  ShoppingBasket,
  ShoppingCart,
  TrendingUp,
  X,
  type LucideIcon,
} from 'lucide-react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuthStore } from '@/lib/auth-store';
import { useApplyTheme } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { Button } from '@/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/ui/dropdown-menu';
import { ThemeMenu } from './ThemeMenu';

interface NavSection {
  label?: string;
  items: { to: string; label: string; icon: LucideIcon; end?: boolean }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    items: [
      { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
      { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
      { to: '/content', label: 'Content', icon: FileText },
      { to: '/calendar', label: 'Calendar', icon: CalendarDays },
    ],
  },
  {
    label: 'Measure',
    items: [
      { to: '/results', label: 'Results', icon: TrendingUp },
      { to: '/suggestions', label: 'Suggestions', icon: Lightbulb },
    ],
  },
  {
    label: 'Shop',
    items: [
      { to: '/products', label: 'Products', icon: Package },
      { to: '/orders', label: 'Orders', icon: ShoppingCart },
      { to: '/channels', label: 'Channels', icon: Radio },
    ],
  },
  {
    items: [{ to: '/settings', label: 'Settings', icon: Settings }],
  },
];

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-1">
      <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <ShoppingBasket className="size-4" aria-hidden />
      </span>
      <span className="text-sm font-semibold tracking-tight">Basket Campaigns</span>
    </div>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-2" aria-label="Main">
      {NAV_SECTIONS.map((section, index) => (
        <div key={section.label ?? index} className="flex flex-col gap-1">
          {section.label && (
            <p className="px-3 pt-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
              {section.label}
            </p>
          )}
          {section.items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <Icon className="size-4 shrink-0" aria-hidden />
              {label}
            </NavLink>
          ))}
        </div>
      ))}
    </nav>
  );
}

function UserMenu() {
  const username = useAuthStore((s) => s.username) ?? 'user';
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex w-full items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-muted"
          aria-label="Account menu"
        >
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/12 text-xs font-semibold text-primary uppercase">
            {username.slice(0, 1)}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{username}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        <DropdownMenuLabel>Signed in as {username}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => {
            logout();
            toast.info('Signed out');
            navigate('/login');
          }}
        >
          <LogOut /> Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  useApplyTheme();
  return (
    <div className="min-h-dvh lg:flex">
      {/* Mobile top bar */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-border bg-background/90 px-4 py-3 backdrop-blur lg:hidden">
        <Button variant="ghost" size="icon" onClick={() => setDrawerOpen(true)} aria-label="Open navigation">
          <Menu />
        </Button>
        <Brand />
        <ThemeMenu />
      </header>

      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-4 border-r border-border bg-card p-3 lg:flex">
        <div className="pt-2">
          <Brand />
        </div>
        <NavItems />
        <div className="mt-auto flex items-center gap-1 border-t border-border pt-3">
          <div className="min-w-0 flex-1">
            <UserMenu />
          </div>
          <ThemeMenu />
        </div>
      </aside>

      {/* Mobile drawer */}
      <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=open]:animate-[overlay-show_150ms_ease-out] lg:hidden" />
          <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col gap-4 border-r border-border bg-card p-4 data-[state=open]:animate-[drawer-in_200ms_ease-out] lg:hidden">
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <div className="flex items-center justify-between">
              <Brand />
              <DialogPrimitive.Close asChild>
                <Button variant="ghost" size="icon" aria-label="Close navigation">
                  <X />
                </Button>
              </DialogPrimitive.Close>
            </div>
            <NavItems onNavigate={() => setDrawerOpen(false)} />
            <div className="mt-auto border-t border-border pt-3">
              <UserMenu />
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  );
}
