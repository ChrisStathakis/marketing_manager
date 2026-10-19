import api from './api';
import type { Paginated } from './types';

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  ordering?: string;
  [key: string]: string | number | boolean | undefined;
}

/** GET a DRF list endpoint, unwrapping the paginated envelope. */
export async function fetchList<T>(url: string, params?: ListParams): Promise<Paginated<T>> {
  const { data } = await api.get<Paginated<T>>(url, { params });
  return data;
}

/** GET a single object. */
export async function fetchOne<T>(url: string, params?: ListParams): Promise<T> {
  const { data } = await api.get<T>(url, { params });
  return data;
}

/** Download any authenticated endpoint as a file. */
export async function downloadFile(url: string, params: ListParams | undefined, filename: string) {
  const res = await api.get<Blob>(url, { params, responseType: 'blob' });
  const blobUrl = URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}

/** Download a CSV endpoint as a file, with the current filters and auth. */
export async function downloadCsv(url: string, params: ListParams | undefined, filename: string) {
  return downloadFile(url, params, filename);
}

/** Shared react-query key factory. */
export const qk = {
  config: ['config'] as const,
  dashboardRoot: ['dashboard'] as const,
  dashboard: (params?: ListParams) => ['dashboard', params] as const,
  campaigns: (params?: ListParams) => ['campaigns', params] as const,
  campaign: (id: number | string) => ['campaign', id] as const,
  channels: (params?: ListParams) => ['channels', params] as const,
  content: (params?: ListParams) => ['content', params] as const,
  metricsRoot: ['metrics'] as const,
  metrics: (params?: ListParams) => ['metrics', params] as const,
  spend: (params?: ListParams) => ['spend', params] as const,
  tasks: (params?: ListParams) => ['tasks', params] as const,
  suggestions: (params?: ListParams) => ['suggestions', params] as const,
  orders: (params?: ListParams) => ['orders', params] as const,
  products: (params?: ListParams) => ['products', params] as const,
  integrations: ['integrations'] as const,
  growthMeta: ['growth', 'meta'] as const,
  growthPlayers: (params?: ListParams) => ['growth', 'players', params] as const,
  growthReport: (params?: ListParams) => ['growth', 'report', params] as const,
  growthInsights: (params?: ListParams) => ['growth', 'insights', params] as const,
  growthTraffic: (params?: ListParams) => ['growth', 'traffic', params] as const,
  statCards: (params?: ListParams) => ['growth', 'cards', params] as const,
  instagramPosts: () => ['growth', 'instagram', 'posts'] as const,
  instagramAnalysis: (params?: ListParams) => ['growth', 'instagram', 'analysis', params] as const,
  instagramComments: (params?: ListParams) => ['growth', 'instagram', 'comments', params] as const,
};
