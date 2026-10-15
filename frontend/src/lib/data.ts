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
export async function fetchOne<T>(url: string): Promise<T> {
  const { data } = await api.get<T>(url);
  return data;
}

/** Download a CSV endpoint as a file, with the current filters and auth. */
export async function downloadCsv(url: string, params: ListParams | undefined, filename: string) {
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

/** Shared react-query key factory. */
export const qk = {
  config: ['config'] as const,
  dashboard: (params?: ListParams) => ['dashboard', params] as const,
  campaigns: (params?: ListParams) => ['campaigns', params] as const,
  campaign: (id: number | string) => ['campaign', id] as const,
  channels: ['channels'] as const,
  content: (params?: ListParams) => ['content', params] as const,
  metrics: (params?: ListParams) => ['metrics', params] as const,
  spend: (params?: ListParams) => ['spend', params] as const,
  tasks: (params?: ListParams) => ['tasks', params] as const,
  suggestions: (params?: ListParams) => ['suggestions', params] as const,
  orders: (params?: ListParams) => ['orders', params] as const,
  products: ['products'] as const,
};
