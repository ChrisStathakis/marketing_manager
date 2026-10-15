import { useEffect } from 'react';
import { create } from 'zustand';

export type Theme = 'light' | 'dark' | 'system';

const STORAGE_KEY = 'theme';

function systemPrefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function apply(theme: Theme) {
  const dark = theme === 'dark' || (theme === 'system' && systemPrefersDark());
  document.documentElement.classList.toggle('dark', dark);
}

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

const initial = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? 'system';

// Apply immediately at import time to avoid a flash of the wrong theme.
apply(initial);

export const useTheme = create<ThemeState>((set) => ({
  theme: initial,
  setTheme(theme) {
    localStorage.setItem(STORAGE_KEY, theme);
    apply(theme);
    set({ theme });
  },
}));

/** Apply the stored theme on load and react to OS changes while in "system" mode. */
export function useApplyTheme() {
  const theme = useTheme((s) => s.theme);
  useEffect(() => {
    apply(theme);
    if (theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => apply('system');
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);
}
