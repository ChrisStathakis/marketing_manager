export interface Campaign {
  id: number; name: string; objective: string; budget: string;
  status: 'draft' | 'planned' | 'active' | 'paused' | 'completed';
  start_date: string | null; end_date: string | null;
  utm_campaign: string; owner: number | null;
}
export interface Channel { id: number; name: string; channel_type: string; handle: string; is_active: boolean }
export interface ContentItem {
  id: number; campaign: number; channel: number | null; title: string;
  copy: string; link: string; utm_source: string; utm_medium: string;
  utm_campaign: string; publish_at: string | null; status: string;
}
export interface DailyMetric {
  id: number; campaign: number; date: string; revenue: string;
  orders: number; spend: string; ctr: number; roas: number;
}
export interface Task {
  id: number; campaign: number | null; title: string; notes: string;
  due_date: string | null; done: boolean; suggestion: number | null;
}
export interface Suggestion {
  id: number; campaign: number; kind: 'rule' | 'ai'; title: string;
  text: string; input_snapshot: Record<string, unknown>; accepted: boolean;
}
export interface DashboardSummary {
  spend: number; revenue: number; orders: number; roas: number;
  campaigns: { id: number; name: string; status: string; spend: number; revenue: number; orders: number; roas: number }[];
}
export interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }
