export type CampaignStatus = 'draft' | 'planned' | 'active' | 'paused' | 'completed';

export interface Campaign {
  id: number;
  name: string;
  objective: string;
  budget: string;
  status: CampaignStatus;
  start_date: string | null;
  end_date: string | null;
  utm_campaign: string;
  owner: number | null;
  created_at: string;
  updated_at: string;
}

export interface Channel {
  id: number;
  name: string;
  channel_type: string;
  handle: string;
  is_active: boolean;
}

export type ContentStatus = 'draft' | 'scheduled' | 'published';

export interface ContentItem {
  id: number;
  campaign: number;
  channel: number | null;
  title: string;
  copy: string;
  asset_url: string;
  link: string;
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
  publish_at: string | null;
  status: ContentStatus;
}

export interface DailyMetric {
  id: number;
  campaign: number;
  date: string;
  revenue: string;
  orders: number;
  spend: string;
  ctr: number;
  roas: number;
}

export interface AdSpend {
  id: number;
  campaign: number;
  channel: number | null;
  date: string;
  spend: string;
  impressions: number;
  clicks: number;
  conversions: number;
}

export interface Task {
  id: number;
  campaign: number | null;
  title: string;
  notes: string;
  due_date: string | null;
  done: boolean;
  suggestion: number | null;
  created_at: string;
}

export interface SuggestionTaskRef {
  id: number;
  title: string;
  done: boolean;
  due_date: string | null;
}

export interface Suggestion {
  id: number;
  campaign: number;
  kind: 'rule' | 'ai';
  title: string;
  text: string;
  input_snapshot: Record<string, unknown>;
  accepted: boolean;
  created_at: string;
  task: SuggestionTaskRef | null;
}

export interface CampaignSummary {
  id: number;
  name: string;
  status: CampaignStatus;
  spend: number;
  revenue: number;
  orders: number;
  roas: number;
}

export interface DashboardPoint {
  date: string;
  revenue: number;
  spend: number;
  orders: number;
}

export interface DashboardDeltas {
  spend: number | null;
  revenue: number | null;
  orders: number | null;
  roas: number | null;
}

export interface DashboardSummary {
  spend: number;
  revenue: number;
  orders: number;
  roas: number;
  series: DashboardPoint[];
  deltas: DashboardDeltas;
  range: { start: string | null; end: string | null };
  campaigns: CampaignSummary[];
}

export interface OrderRef {
  id: number;
  external_id: string;
  campaign: number | null;
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
  total: string;
  ordered_at: string | null;
}

export interface Product {
  id: number;
  external_id: string;
  name: string;
  price: string;
  url: string;
  updated_at: string;
}

export interface AppConfig {
  registration_enabled: boolean;
}

export interface Integration {
  id: string;
  label: string;
  summary: string;
  description: string;
  env_var: string;
  used_by: string[];
  where_to_get: string;
  steps: string[];
  security_note: string;
  configured: boolean;
  source: 'database' | 'env' | null;
  key_hint: string | null;
  stored: boolean;
  stored_unreadable: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ImportResult {
  created: number;
  updated: number;
  error_count: number;
  errors: { row: number; error: string }[];
}
