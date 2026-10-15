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

export interface Suggestion {
  id: number;
  campaign: number;
  kind: 'rule' | 'ai';
  title: string;
  text: string;
  input_snapshot: Record<string, unknown>;
  accepted: boolean;
  created_at: string;
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

export interface DashboardSummary {
  spend: number;
  revenue: number;
  orders: number;
  roas: number;
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
