import { useState } from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import {
  BookOpen,
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
  ShoppingCart,
  Sparkles,
  TrendingUp,
  X,
  type LucideIcon,
} from 'lucide-react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
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
    label: 'Grow',
    items: [
      { to: '/growth', label: 'Growth studio', icon: Sparkles },
      { to: '/playbooks', label: 'Playbooks', icon: BookOpen },
    ],
  },
  {
    label: 'Plan',
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

const FLAT_NAV = NAV_SECTIONS.flatMap((s) => s.items);

/** Computed once at app load — stable across re-renders. */
const CURRENT_YEAR = new Date().getFullYear();

export function Brand({ className }: { className?: string }) {
  return (
    <span className={cn('select-none text-[1.35rem] leading-none font-extrabold tracking-[-0.06em]', className)}>
      social<span className="text-gold">.</span>
    </span>
  );
}

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1" aria-label="Main">
      {NAV_SECTIONS.map((section, index) => (
        <div key={section.label ?? index} className="flex flex-col gap-1">
          {section.label && <p className="eyebrow mt-5 mb-1.5 px-3">{section.label}</p>}
          {section.items.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-[9px] px-3 py-2 text-sm font-medium transition-colors duration-150',
                  isActive
                    ? 'bg-primary-solid font-semibold text-primary-foreground shadow-soft'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-primary',
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

function SidebarNote() {
  return (
    <div className="rounded-field bg-sidebar-note p-4">
      <span className="eyebrow">Room to grow</span>
      <p className="mt-2 text-[0.78rem] leading-relaxed text-muted-foreground">
        A clear view of today.
        <br />A better plan for tomorrow.
      </p>
    </div>
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
          className="flex items-center gap-2.5 rounded-full p-1 pr-1 text-left transition-colors hover:bg-muted sm:pr-3"
          aria-label="Account menu"
        >
          <span className="flex size-8.5 shrink-0 items-center justify-center rounded-full bg-sage text-sm font-bold text-primary uppercase">
            {username.slice(0, 1)}
          </span>
          <span className="hidden max-w-28 truncate text-sm font-semibold sm:block">{username}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
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
  const location = useLocation();
  useApplyTheme();

  const section =
    FLAT_NAV.find((i) => (i.end ? location.pathname === i.to : location.pathname.startsWith(i.to)))?.label ?? 'Dashboard';

  return (
    <div className="min-h-dvh lg:flex">
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh w-62 shrink-0 flex-col border-r border-border bg-sidebar p-4 lg:flex">
        <div className="px-2 pt-2">
          <Brand />
        </div>
        <p className="eyebrow mt-9 mb-3 px-3">Your shop, in focus</p>
        <div className="min-h-0 flex-1 overflow-y-auto pb-4">
          <NavItems />
        </div>
        <div className="border-t border-border/70 pt-4">
          <SidebarNote />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-border bg-topbar/95 px-4 backdrop-blur sm:px-6 lg:h-18 lg:px-10">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setDrawerOpen(true)} aria-label="Open navigation">
            <Menu />
          </Button>
          <div className="hidden min-w-0 items-center gap-2 text-sm lg:flex">
            <span className="text-muted-foreground">Your workspace</span>
            <span className="text-muted-foreground/60">/</span>
            <strong className="truncate font-semibold tracking-tight">{section}</strong>
          </div>
          <div className="lg:hidden">
            <Brand className="text-xl" />
          </div>
          <div className="ml-auto flex items-center gap-1">
            <ThemeMenu />
            <UserMenu />
          </div>
        </header>

        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-7 sm:px-6 lg:px-10">
          <div key={location.pathname} className="enter">
            <Outlet />
          </div>
        </main>

        <footer className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 pb-6 text-xs text-muted-foreground sm:px-6 lg:px-10">
          <span>
            social<span className="text-gold">.</span>{' '}
            <span className="text-muted-foreground/80">Made for the shop you grow.</span>
          </span>
          <span>{CURRENT_YEAR}</span>
        </footer>
      </div>

      {/* Mobile drawer */}
      <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[#0b1710]/55 backdrop-blur-[2px] data-[state=open]:animate-[overlay-show_150ms_ease-out] lg:hidden" />
          <DialogPrimitive.Content className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-border bg-sidebar p-4 data-[state=open]:animate-[drawer-in_200ms_ease-out] lg:hidden">
            <DialogPrimitive.Title className="sr-only">Navigation</DialogPrimitive.Title>
            <div className="flex items-center justify-between px-2 pt-2">
              <Brand />
              <DialogPrimitive.Close asChild>
                <Button variant="ghost" size="icon" aria-label="Close navigation">
                  <X />
                </Button>
              </DialogPrimitive.Close>
            </div>
            <p className="eyebrow mt-6 mb-2 px-3">Your shop, in focus</p>
            <div className="min-h-0 flex-1 overflow-y-auto pb-4">
              <NavItems onNavigate={() => setDrawerOpen(false)} />
            </div>
            <div className="border-t border-border/70 pt-4">
              <SidebarNote />
            </div>
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
    </div>
  );
}
