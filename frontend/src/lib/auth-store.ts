import { create } from 'zustand';
import axios from 'axios';

interface AuthState {
  access: string | null;
  refreshToken: string | null;
  username: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  refresh: () => Promise<boolean>;
}

const base = () => import.meta.env.VITE_API_URL ?? '/api';

export const useAuthStore = create<AuthState>((set, get) => ({
  access: localStorage.getItem('access'),
  refreshToken: localStorage.getItem('refresh'),
  username: localStorage.getItem('username'),
  async login(username, password) {
    try {
      const { data } = await axios.post(`${base()}/token/`, { username, password });
      localStorage.setItem('access', data.access);
      localStorage.setItem('refresh', data.refresh);
      localStorage.setItem('username', username);
      set({ access: data.access, refreshToken: data.refresh, username });
      return true;
    } catch {
      return false;
    }
  },
  logout() {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    localStorage.removeItem('username');
    set({ access: null, refreshToken: null, username: null });
  },
  async refresh() {
    const rt = get().refreshToken;
    if (!rt) return false;
    try {
      const { data } = await axios.post(`${base()}/token/refresh/`, { refresh: rt });
      localStorage.setItem('access', data.access);
      set({ access: data.access });
      return true;
    } catch {
      get().logout();
      return false;
    }
  },
}));
