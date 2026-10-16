import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/lib/theme';
import { Brand } from './AppShell';

/** Decorative landscape from the reference app's login illustration. */
function Landscape({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 500 250" preserveAspectRatio="xMidYMax slice" fill="none" aria-hidden="true">
      <circle cx="385" cy="70" r="35" fill="#d5bd7e" />
      <path d="M0 165Q150 65 300 160T600 160V250H0Z" fill="#a9ba8b" />
      <path d="M0 200Q180 110 360 190T550 185V250H0Z" fill="#708e61" />
      <path d="M210 250Q320 155 510 180V250Z" fill="#42684b" />
      <g stroke="#c9d5ad" strokeWidth="2" opacity=".65">
        <path d="M250 250Q350 180 500 195M300 250Q380 195 500 212M365 250Q425 213 500 230" />
      </g>
      <path d="M295 153V109L321 86L347 109V164" fill="#f3eed6" />
      <path d="M287 112L321 81L355 112" stroke="#42684b" strokeWidth="6" />
      <path d="M315 155V133H328V158" fill="#708e61" />
    </svg>
  );
}

/** Light/dark flipper for the dark story panel (same idea as the reference login toggle). */
function StoryThemeToggle() {
  const { theme, setTheme } = useTheme();
  const isDark =
    theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  return (
    <button
      type="button"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="flex size-9 items-center justify-center rounded-full border border-white/25 text-[#e5eddd] transition-colors hover:bg-white/10 hover:text-white"
    >
      {isDark ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
    </button>
  );
}

/** Split auth screen: dark story panel (desktop) + form side. */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden flex-col justify-between overflow-hidden bg-[#16281f] p-10 text-[#e5eddd] lg:flex xl:p-14">
        <div className="relative z-1 flex items-center justify-between">
          <Brand className="text-3xl text-[#f0f1e2]" />
          <StoryThemeToggle />
        </div>
        <div className="relative z-1 max-w-md">
          <h1 className="text-[clamp(2rem,3.4vw,2.9rem)] leading-[1.08] font-semibold tracking-[-0.04em] text-[#f0f1e2]">
            Plan the posts.
            <br />
            Track the spend.
            <br />
            Grow the shop.
          </h1>
          <p className="mt-5 max-w-sm text-[0.95rem] leading-relaxed text-[#b9c9b4]">
            A thoughtful home for your campaigns, content, and the numbers that make them work.
          </p>
        </div>
        <p className="relative z-1 text-[0.65rem] font-bold tracking-[0.16em] text-[#9fb59a] uppercase">Your shop, in focus.</p>
        <Landscape className="pointer-events-none absolute right-[-4%] bottom-[-2%] w-[86%] opacity-90" />
      </section>
      <main className="flex items-center justify-center bg-background px-4 py-10 lg:px-10">
        <div className="enter w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Brand className="text-2xl" />
          </div>
          {children}
        </div>
      </main>
    </div>
  );
}
