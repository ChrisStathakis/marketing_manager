export type CampaignStatus = 'draft' | 'planned' | 'active' | 'paused' | 'completed';

export interface Campaign {
  id: number;
  name: string;
  objective: string;
  budget: string;
  status: CampaignStatus;
  playbook: number | null;
  playbook_name?: string;
  round_label: string;
  locales: string[];
  platforms: string[];
  start_date: string | null;
  end_date: string | null;
  utm_campaign: string;
  landing_path: string;
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

export interface ContentAsset {
  id: number;
  content_item: number;
  kind: 'image' | 'video' | 'link' | 'other';
  file: string;
  file_url: string;
  url: string;
  position: number;
  alt_text: string;
  created_at: string;
}

export interface ContentItem {
  id: number;
  campaign: number;
  channel: number | null;
  card_set: number | null;
  title: string;
  copy: string;
  asset_url: string;
  link: string;
  utm_source: string;
  utm_medium: string;
  utm_campaign: string;
  utm_content: string;
  locale: string;
  locale_label?: string;
  format: string;
  format_label?: string;
  content_kind: string;
  thread: string[];
  notes: string;
  publish_at: string | null;
  status: ContentStatus;
  assets: ContentAsset[];
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
  content_formats: [string, string][];
  playbook_platforms: [string, string][];
  content_locales: [string, string][];
  sizes: Record<string, [number, number]>;
  platforms: [string, string][];
  log_platforms: [string, string][];
  locales: string[];
  full_locales: string[];
  metrics: GrowthMetric[];
  kpi_metrics: [string, string][];
  hashtag_sets: HashtagSet[];
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
  rank?: number;
  team?: string;
  team_full?: string;
  record?: string;
  net?: string;
  team_id?: number;
}

/** The numbers behind one card, as produced by the API and stored on save. */
export interface CardSpec {
  kind: string;
  layout?: 'table' | string;
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
  thread?: string[];
}

export interface CaptionResponse {
  spec: CardSpec;
  link: string;
  drafts: CaptionDraft[];
}

export interface GrowthStatCard {
  id: number;
  campaign: number | null;
  card_set: number | null;
  position: number;
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
  format: string;
  format_label: string;
  locale: string;
  locale_label: string;
  utm_content: string;
  url: string;
  posted_at: string | null;
  impressions: number;
  reach: number;
  engagements: number;
  saves: number;
  shares: number;
  comments: number;
  profile_visits: number;
  clicks: number;
  signups: number;
  upvote_ratio: number | null;
  engagement_rate: number | null;
  click_rate: number | null;
  save_rate: number | null;
  share_rate: number | null;
  notes: string;
  created_at: string;
}

/** Rolled-up numbers for one platform, card kind or metric. */
export interface GrowthStats {
  posts: number;
  impressions: number;
  reach: number;
  engagements: number;
  saves: number;
  shares: number;
  comments: number;
  profile_visits: number;
  clicks: number;
  signups: number;
  upvote_ratio: number | null;
  engagement_rate: number | null;
  click_rate: number | null;
  save_rate: number | null;
  share_rate: number | null;
}

export interface GrowthReportRow extends GrowthStats {
  /** Set on the platform breakdown only. */
  platform?: string;
  /** Set on the kind breakdown only. */
  kind?: string;
  /** Set on the metric breakdown only. */
  metric?: string;
  format?: string;
  locale?: string;
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

export interface GrowthTrafficCampaign {
  campaign?: string;
  content?: string;
  source: string;
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
  by_campaign: GrowthTrafficCampaign[];
  by_content: GrowthTrafficCampaign[];
}

export interface GrowthTrafficSnapshot {
  id: number;
  date: string;
  source: string;
  medium: string;
  campaign: string;
  content: string;
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

export interface GrowthSearchTotals {
  clicks: number;
  impressions: number;
  /** Fraction, e.g. 0.052 for 5.2%. */
  ctr: number;
  /** Impression-weighted average position. */
  position: number;
}

export interface GrowthSearchRow extends GrowthSearchTotals {
  page_path?: string;
  page_url?: string;
  query?: string;
}

export interface GrowthSearchCampaign {
  window: { start: string; end: string };
  pages: string[];
  totals: GrowthSearchTotals;
  by_page: GrowthSearchRow[];
  matched: boolean;
  warning: string;
}

/**
 * Search Console has no UTM dimension. When a campaign is selected, its
 * section is *assisted* organic search for the pages the campaign linked to.
 */
export interface GrowthSearchConsoleReport {
  window: { start: string; end: string };
  previous_window: { start: string; end: string };
  totals: GrowthSearchTotals;
  previous_totals: GrowthSearchTotals;
  by_page: GrowthSearchRow[];
  by_query: GrowthSearchRow[];
  campaign: GrowthSearchCampaign | null;
  data_through: string | null;
  data_lag_days: number;
  configured: boolean;
  site_url: string;
  last_synced_at: string | null;
}

export interface GrowthSearchSyncResult {
  created: number;
  updated: number;
  rows: number;
  pages: number;
  queries: number;
  clicks: number;
  impressions: number;
  start: string | null;
  end: string | null;
  site_url: string;
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

export interface KpiTarget {
  id: number;
  campaign: number;
  metric: string;
  metric_label: string;
  target: number;
  window_start: string | null;
  window_end: string | null;
  notes: string;
  created_at: string;
}

export interface KpiTargetProgress extends KpiTarget {
  actual: number | null;
  progress: number | null;
  remaining: number | null;
  met: boolean;
}

export interface HashtagSet {
  id: number;
  name: string;
  locale: string;
  platform: string;
  tags: string[];
  is_default: boolean;
  created_at: string;
}

export interface Boost {
  id: number;
  campaign: number | null;
  content_item: number | null;
  platform: string;
  platform_label: string;
  status: 'planned' | 'running' | 'done' | 'cancelled';
  status_label: string;
  objective: string;
  daily_budget: string;
  total_budget: string;
  start_date: string | null;
  end_date: string | null;
  targeting: Record<string, unknown>;
  cpa_target: string | null;
  notes: string;
  created_at: string;
}

export interface PlaybookSlot {
  id?: number;
  playbook?: number;
  order: number;
  day_offset: number;
  time: string;
  platform: string;
  format: string;
  content_kind: string;
  locales: string[];
  title_template: string;
  brief: string;
  utm_content_template: string;
  asset_required: boolean;
  paid_budget: string;
  is_task_only: boolean;
  notes: string;
}

export interface Playbook {
  id: number;
  name: string;
  description: string;
  default_locales: string[];
  default_platforms: string[];
  is_seeded: boolean;
  slot_count: number;
  slots: PlaybookSlot[];
  created_at: string;
  updated_at: string;
}

export interface PlaybookPreviewItem {
  title: string;
  kind: string;
  platform: string;
  platform_label: string;
  format: string;
  locale: string;
  publish_at: string;
  link: string;
  utm_content: string;
  asset_required: boolean;
  paid_budget: number;
  is_task_only: boolean;
  channel: string;
  missing_channel: boolean;
}

export interface PlaybookPreview {
  playbook: Playbook;
  start_date: string;
  end_date: string;
  round_label: string;
  locales: string[];
  platforms: string[];
  landing_path: string;
  count: number;
  by_platform: { platform: string; label: string; count: number }[];
  by_locale: Record<string, number>;
  items: PlaybookPreviewItem[];
  missing_channels: string[];
}

export interface PlaybookRunResult {
  campaign: Campaign;
  created: number;
  skipped: number;
  tasks: number;
  task_only: number;
  missing_channels: string[];
  targets_created: number;
  boosts_created: number;
  start_date: string;
  end_date: string;
  items: ContentItem[];
}

export interface CardSet {
  id: number;
  campaign: number | null;
  kind: string;
  format: string;
  title: string;
  subtitle: string;
  payload: Record<string, unknown>;
  slides: GrowthStatCard[];
  created_at: string;
}

export interface GrowthTeam {
  team_id: number;
  team_title: string;
  season_title: string;
  games: number;
  wins: number;
  losses: number;
  record: string;
  offensive_rating: number | null;
  defensive_rating: number | null;
  net_rating: number | null;
  avg_pace: number | null;
  ts_pct: number | null;
  efg_pct: number | null;
  tov_pct: number | null;
  oreb_pct: number | null;
}

export interface GrowthReport {
  days: number;
  since: string;
  previous_since: string;
  campaign: Campaign | null;
  totals: GrowthStats;
  previous_totals: GrowthStats;
  kpi_targets: KpiTargetProgress[];
  by_platform: GrowthReportRow[];
  by_kind: GrowthReportRow[];
  by_format: GrowthReportRow[];
  by_locale: GrowthReportRow[];
  by_metric: GrowthReportRow[];
  trend: GrowthTrendRow[];
  traffic: GrowthTrafficSummary;
  traffic_configured: boolean;
  search_console: GrowthSearchConsoleReport;
  can_sync: boolean;
  best_posts: PostPerformance[];
}
