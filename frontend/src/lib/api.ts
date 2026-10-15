import axios from 'axios';
import { useAuthStore } from './auth-store';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL ?? '/api' });

api.interceptors.request.use((cfg) => {
  const token = useAuthStore.getState().access;
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config as (typeof err.config & { _retry?: boolean });
    if (err.response?.status === 401 && !orig._retry) {
      orig._retry = true;
      const ok = await useAuthStore.getState().refresh();
      if (ok) {
        orig.headers.Authorization = `Bearer ${useAuthStore.getState().access}`;
        return api(orig);
      }
    }
    return Promise.reject(err);
  },
);

export default api;
