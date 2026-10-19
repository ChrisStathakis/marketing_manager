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
  users_exist: boolean;
}

export interface IntegrationField {
  name: string;
  label: string;
  secret: boolean;
  multiline?: boolean;
  min_length?: number;
  placeholder?: string;
  prefix?: string;
  hint?: string;
}

export interface IntegrationConfigField {
  name: string;
  label: string;
  env_var?: string;
  placeholder?: string;
  required?: boolean;
  hint?: string;
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
  fields?: IntegrationField[];
  config_fields?: IntegrationConfigField[];
  sync_endpoint?: string;
  configured: boolean;
  source: 'database' | 'env' | null;
  key_hint: string | null;
  stored: boolean;
  stored_unreadable: boolean;
  config: Record<string, string>;
  last_synced_at: string | null;
  last_sync_error: string;
  updated_at: string | null;
  updated_by: string | null;
}

/** Response of POST /api/integrations/google-analytics/sync/. */
export interface SyncResult {
  created: number;
  updated: number;
  skipped: number;
  rows: number;
  unmatched: string[];
  start: string | null;
  end: string | null;
  last_synced_at: string | null;
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

/** Response of POST /api/backup/restore/. */
export interface RestoreResult {
  kind: 'json' | 'database';
  detail: string;
  restored?: Record<string, number>;
}

// -- Organic growth studio -------------------------------------------------

export interface GrowthSeason {
  id: number;
  title: string;
  season_id: string;
  active: boolean;
  default_season: boolean;
}

export interface GrowthMetric {
  key: string;
  label: string;
  short: string;
  digits: number;
}

export interface GrowthMeta {
  seasons: GrowthSeason[];
  default_season: GrowthSeason | null;
  priority_teams: Record<string, string[]>;
  country_labels: Record<string, string>;
  kinds: [string, string][];
  formats: [string, string][];
  sizes: Record<string, [number, number]>;
  platforms: [string, string][];
  log_platforms: [string, string][];
  locales: string[];
  full_locales: string[];
  metrics: GrowthMetric[];
  site_url: string;
  /** GA4 session source → studio platform, for reading the traffic table. */
  sources: Record<string, string>;
  ga4_configured: boolean;
  instagram_configured: boolean;
  instagram_enabled: boolean;
  can_sync: boolean;
  warning: string;
}

export interface InstagramTrackedPost {
  id: number;
  url: string;
  shortcode: string;
  media_pk: number;
  owner_username: string;
  caption: string;
  comment_count: number;
  comments_stored: number;
  status: string;
  status_label: string;
  error: string;
  last_scraped_at: string | null;
  created_at: string;
}

export interface InstagramComment {
  id: number;
  post: number;
  comment_pk: string;
  author_username: string;
  author_pk: string;
  author_full_name: string;
  text: string;
  commented_at: string | null;
  like_count: number;
  child_count: number;
  fetched_at: string;
}

export interface InstagramCommenter {
  author_username: string;
  comments: number;
  posts: number;
}

export interface InstagramAnalysis {
  totals: {
    comments: number;
    commenters: number;
    repeat_commenters: number;
    posts: number;
  };
  top_commenters: InstagramCommenter[];
  repeat_commenters: InstagramCommenter[];
  by_post: {
    id: number;
    shortcode: string;
    owner_username: string;
    stored: number;
    reported: number;
    last_scraped_at: string | null;
  }[];
}

export interface CardRow {
  key?: string;
  label?: string;
  value?: string;
  note?: string;
  note_metric?: string;
  note_team?: string;
  left?: string;
  right?: string;
  winner?: 'left' | 'right' | null;
}

/** The numbers behind one card, as produced by the API and stored on save. */
export interface CardSpec {
  kind: string;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  headline?: string;
  headline_key?: string;
  headline_label?: string;
  headline_note?: string;
  columns?: string[];
  rows: CardRow[];
  footer?: string;
  accent?: string;
}

export interface CaptionDraft {
  platform: string;
  locale: string;
  title: string;
  text: string;
  hashtags: string[];
  limit: number;
  length: number;
  within_limit: boolean;
  localisation: 'full' | 'hook';
}

export interface CaptionResponse {
  spec: CardSpec;
  link: string;
  drafts: CaptionDraft[];
}

export interface GrowthStatCard {
  id: number;
  campaign: number | null;
  kind: string;
  format: string;
  title: string;
  subtitle: string;
  payload: CardSpec;
  image_url: string;
  created_at: string;
}

export interface PostPerformance {
  id: number;
  campaign: number | null;
  content_item: number | null;
  platform: string;
  platform_label: string;
  kind: string;
  kind_label: string;
  metric_key: string;
  metric_label: string;
  url: string;
  posted_at: string | null;
  impressions: number;
  engagements: number;
  comments: number;
  clicks: number;
  engagement_rate: number | null;
  click_rate: number | null;
  notes: string;
  created_at: string;
}

/** Rolled-up numbers for one platform, card kind or metric. */
export interface GrowthStats {
  posts: number;
  impressions: number;
  engagements: number;
  comments: number;
  clicks: number;
  engagement_rate: number | null;
  click_rate: number | null;
}

export interface GrowthReportRow extends GrowthStats {
  /** Set on the platform breakdown only. */
  platform?: string;
  /** Set on the kind breakdown only. */
  kind?: string;
  /** Set on the metric breakdown only. */
  metric?: string;
  label: string;
  best_post?: PostPerformance | null;
}

export interface GrowthTrendRow {
  platform: string;
  label: string;
  clicks: number;
  previous_clicks: number;
  click_rate: number | null;
  previous_click_rate: number | null;
  delta_click_rate: number | null;
  posts: number;
  previous_posts: number;
  direction: 'up' | 'down' | 'flat';
}

export interface GrowthTrafficPlatform {
  platform: string;
  label: string;
  sessions: number;
  engaged_sessions: number;
  engagement_rate: number | null;
  sources: string[];
}

export interface GrowthTrafficSource {
  source: string;
  medium: string;
  platform: string | null;
  sessions: number;
  engaged_sessions: number;
  engagement_rate: number | null;
}

export interface GrowthTrafficSummary {
  totals: {
    sessions: number;
    social_sessions: number;
    engaged_sessions: number;
    users: number;
    views: number;
  };
  by_platform: GrowthTrafficPlatform[];
  by_source: GrowthTrafficSource[];
}

export interface GrowthTrafficSnapshot {
  id: number;
  date: string;
  source: string;
  medium: string;
  platform: string | null;
  sessions: number;
  engaged_sessions: number;
  users: number;
  views: number;
  engagement_rate: number | null;
  fetched_at: string;
}

export interface GrowthTrafficResponse {
  days: number;
  since: string;
  summary: GrowthTrafficSummary;
  results: GrowthTrafficSnapshot[];
  configured: boolean;
  can_sync: boolean;
  last_synced_at: string | null;
}

export interface GrowthInsight {
  id: string;
  severity: 'warn' | 'win' | 'info';
  title: string;
  detail: string;
  evidence: string[];
  action?: {
    target: 'log' | 'plan' | 'builder' | 'traffic';
    kind?: string;
    metric?: string;
  };
}

export interface GrowthNextCard {
  kind: string;
  metric: string | null;
  country: string | null;
  reason: string;
}

export interface GrowthInsights {
  days: number;
  since: string;
  previous_since: string;
  totals: GrowthStats;
  previous_totals: GrowthStats;
  insights: GrowthInsight[];
  next_cards: GrowthNextCard[];
}

export interface GrowthReport {
  days: number;
  since: string;
  previous_since: string;
  totals: GrowthStats;
  previous_totals: GrowthStats;
  by_platform: GrowthReportRow[];
  by_kind: GrowthReportRow[];
  by_metric: GrowthReportRow[];
  trend: GrowthTrendRow[];
  traffic: GrowthTrafficSummary;
  traffic_configured: boolean;
  can_sync: boolean;
  best_posts: PostPerformance[];
}
