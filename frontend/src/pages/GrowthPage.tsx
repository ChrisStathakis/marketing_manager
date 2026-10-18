import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  CalendarPlus,
  Copy,
  Download,
  Loader2,
  Minus,
  RefreshCw,
  Save,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wand2,
} from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { fetchList, fetchOne, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatDate, formatNumber, toDateInputValue } from '@/lib/format';
import { cn } from '@/lib/utils';
import type {
  Campaign,
  CaptionDraft,
  CaptionResponse,
  CardSpec,
  GrowthInsight,
  GrowthInsights,
  GrowthMeta,
  GrowthNextCard,
  GrowthReport,
  GrowthReportRow,
  GrowthStatCard,
  GrowthTrafficResponse,
  GrowthTrendRow,
  PostPerformance,
} from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { EmptyState } from '@/ui/empty-state';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';
import { Tabs, TabsList, TabsTrigger } from '@/ui/tabs';

interface PlayerOption {
  id: number;
  name: string;
  team: string;
}

interface PlanResult {
  created: number;
  skipped: number;
  tasks: number;
  missing_channels: string[];
  week_start: string;
  warning: string;
}

const AUTO = 'auto';
const NONE = 'none';

/** Insight severity → the alert variant that already encodes it. */
const SEVERITY_VARIANT: Record<GrowthInsight['severity'], 'info' | 'success' | 'destructive'> = {
  warn: 'destructive',
  win: 'success',
  info: 'info',
};

/** Percentages come back as 0-1 fractions from the report. */
function rate(value: number | null): string {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`;
}

function StatBox({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-field border border-border bg-surface-alt p-3">
      <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/** Change in click rate between the current window and the one before it. */
function TrendDelta({ row }: { row: GrowthTrendRow | undefined }) {
  if (!row || row.delta_click_rate == null) {
    return <span className="text-muted-foreground">—</span>;
  }
  const Icon = row.direction === 'up' ? TrendingUp : row.direction === 'down' ? TrendingDown : Minus;
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 tabular-nums',
        row.direction === 'up' && 'text-success',
        row.direction === 'down' && 'text-destructive',
        row.direction === 'flat' && 'text-muted-foreground',
      )}
      title={`Was ${rate(row.previous_click_rate)} in the previous window`}
    >
      <Icon className="size-3.5" />
      {(row.delta_click_rate * 100).toFixed(2)} pp
    </span>
  );
}

function BreakdownTable({ rows, group }: { rows: GrowthReportRow[]; group: 'kind' | 'metric' }) {
  if (!rows.length) {
    return (
      <p className="text-sm text-muted-foreground">
        {group === 'kind'
          ? 'Log a post with its card type and this ranks the formats.'
          : 'Log a post with its metric and this tells you which subject clicks.'}
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{group === 'kind' ? 'Card type' : 'Metric'}</TableHead>
            <TableHead className="text-right">Posts</TableHead>
            <TableHead className="text-right">Impressions</TableHead>
            <TableHead className="text-right">Click rate</TableHead>
            <TableHead className="text-right">Engagement</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row[group] ?? row.label}>
              <TableCell className="font-medium">{row.label}</TableCell>
              <TableCell className="text-right">{formatNumber(row.posts)}</TableCell>
              <TableCell className="text-right">{formatNumber(row.impressions)}</TableCell>
              <TableCell className="text-right">{rate(row.click_rate)}</TableCell>
              <TableCell className="text-right">{rate(row.engagement_rate)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export default function GrowthPage() {
  const queryClient = useQueryClient();

  const meta = useQuery({
    queryKey: qk.growthMeta,
    queryFn: () => fetchOne<GrowthMeta>('/growth/meta/'),
    staleTime: 10 * 60 * 1000,
  });
  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 100 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 100, ordering: '-created_at' }),
  });

  const [season, setSeason] = useState('');
  const [kind, setKind] = useState('metric');
  const [metric, setMetric] = useState(AUTO);
  const [country, setCountry] = useState(AUTO);
  const [player, setPlayer] = useState(AUTO);
  const [teamA, setTeamA] = useState(AUTO);
  const [teamB, setTeamB] = useState(AUTO);
  const [format, setFormat] = useState('x');
  const [campaignId, setCampaignId] = useState('');

  const [spec, setSpec] = useState<CardSpec | null>(null);
  const [link, setLink] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [fetchedAt, setFetchedAt] = useState('');
  const [stale, setStale] = useState(false);
  const [dataWarning, setDataWarning] = useState('');
  const [captionPlatform, setCaptionPlatform] = useState('x');
  const [captionLocale, setCaptionLocale] = useState('en');
  const bootstrapped = useRef(false);

  const [roundLabel, setRoundLabel] = useState('');
  const [weekStart, setWeekStart] = useState(() => toDateInputValue(new Date()));
  const [planResult, setPlanResult] = useState<PlanResult | null>(null);

  const [reportDays, setReportDays] = useState(30);
  const [logPlatform, setLogPlatform] = useState('x');
  const [logDate, setLogDate] = useState(() => toDateInputValue(new Date()));
  const [logImpressions, setLogImpressions] = useState('');
  const [logEngagements, setLogEngagements] = useState('');
  const [logClicks, setLogClicks] = useState('');
  const [logUrl, setLogUrl] = useState('');
  const [logKind, setLogKind] = useState(NONE);
  const [logMetric, setLogMetric] = useState(NONE);

  // Derived selection: the page defaults to the active season and newest
  // campaign without an extra render pass.
  const activeSeason = season || (meta.data?.default_season ? String(meta.data.default_season.id) : '');
  const activeCampaignId =
    campaignId || (campaigns.data?.results.length ? String(campaigns.data.results[0].id) : '');

  const selectedCampaign = useMemo(
    () => campaigns.data?.results.find((item) => String(item.id) === activeCampaignId),
    [campaigns.data, activeCampaignId],
  );

  const players = useQuery({
    queryKey: qk.growthPlayers({ season: activeSeason, metric, country }),
    queryFn: () =>
      fetchOne<{ results: PlayerOption[]; teams: string[] }>('/growth/players/', {
        season: activeSeason,
        metric: metric === AUTO ? undefined : metric,
        country: country === AUTO ? undefined : country,
        ordering: metric === AUTO ? '-score' : `-${metric}`,
        page_size: 80,
      }),
    enabled: Boolean(activeSeason),
  });

  const suggestParams = useMemo(
    () => ({
      season: activeSeason,
      kind,
      country: country === AUTO ? undefined : country,
      metric: metric === AUTO ? undefined : metric,
      player: player === AUTO ? undefined : player,
      teams: kind === 'matchup' ? [teamA, teamB].filter((team) => team !== AUTO).join(',') : undefined,
      utm_campaign: selectedCampaign?.utm_campaign || 'organic-growth',
    }),
    [activeSeason, kind, country, metric, player, teamA, teamB, selectedCampaign],
  );

  const suggest = useMutation({
    mutationFn: async (overrides?: Record<string, string | undefined>) => {
      const { data } = await api.get<{
        spec: CardSpec;
        link: string;
        season: { title?: string } | null;
        fetched_at: string;
        stale: boolean;
        warning: string;
      }>('/growth/suggest/', { params: { ...suggestParams, ...overrides } });
      return data;
    },
    onSuccess: (data) => {
      setSpec(data.spec);
      setLink(data.link);
      setFetchedAt(data.fetched_at ?? '');
      setStale(Boolean(data.stale));
      setDataWarning(data.warning ?? '');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
  const requestSuggest = suggest.mutate;

  const preview = useMutation({
    mutationFn: async ({ cardSpec, cardFormat }: { cardSpec: CardSpec; cardFormat: string }) => {
      const { data } = await api.post<Blob>(
        '/growth/cards/preview/',
        { spec: cardSpec, format: cardFormat },
        { responseType: 'blob' },
      );
      return data;
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
  const requestPreview = preview.mutate;

  const captions = useMutation({
    mutationFn: async ({ cardSpec, utmCampaign }: { cardSpec: CardSpec; utmCampaign: string }) => {
      const { data } = await api.post<CaptionResponse>('/growth/captions/', {
        spec: cardSpec,
        utm_campaign: utmCampaign,
      });
      return data;
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });
  const requestCaptions = captions.mutate;

  const saveCard = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<GrowthStatCard>('/cards/', {
        spec,
        format,
        campaign: activeCampaignId ? Number(activeCampaignId) : null,
      });
      return data;
    },
    onSuccess: () => toast.success('Card saved to the library'),
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const seedPlan = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<PlanResult>('/growth/plan/', {
        campaign: Number(activeCampaignId),
        round_label: roundLabel || 'this round',
        start_date: weekStart,
        season: activeSeason,
      });
      return data;
    },
    onSuccess: (data) => {
      setPlanResult(data);
      toast.success(`${data.created} posts added to the calendar`);
      void queryClient.invalidateQueries({ queryKey: qk.content() });
      void queryClient.invalidateQueries({ queryKey: qk.tasks() });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const logPost = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<PostPerformance>('/performance/', {
        platform: logPlatform,
        kind: logKind === NONE ? '' : logKind,
        metric_key: logMetric === NONE ? '' : logMetric,
        posted_at: new Date(`${logDate}T12:00:00`).toISOString(),
        impressions: Number(logImpressions) || 0,
        engagements: Number(logEngagements) || 0,
        clicks: Number(logClicks) || 0,
        url: logUrl,
        campaign: activeCampaignId ? Number(activeCampaignId) : null,
      });
      return data;
    },
    onSuccess: () => {
      toast.success('Post logged');
      setLogImpressions('');
      setLogEngagements('');
      setLogClicks('');
      setLogUrl('');
      void queryClient.invalidateQueries({ queryKey: ['growth', 'report'] });
      void queryClient.invalidateQueries({ queryKey: ['growth', 'insights'] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const report = useQuery({
    queryKey: qk.growthReport({ days: reportDays }),
    queryFn: () => fetchOne<GrowthReport>('/growth/report/', { days: reportDays }),
  });

  const insights = useQuery({
    queryKey: qk.growthInsights({ days: reportDays }),
    queryFn: () => fetchOne<GrowthInsights>('/growth/insights/', { days: reportDays }),
  });

  const traffic = useQuery({
    queryKey: qk.growthTraffic({ days: reportDays }),
    queryFn: () => fetchOne<GrowthTrafficResponse>('/growth/traffic/', { days: reportDays }),
  });

  const syncTraffic = useMutation({
    mutationFn: async (days: number) => {
      const { data } = await api.post<{
        created: number;
        updated: number;
        sessions: number;
        social_sessions: number;
        other_sources: string[];
      }>('/growth/traffic/sync/', { days });
      return data;
    },
    onSuccess: (result) => {
      toast.success(`${formatNumber(result.sessions)} sessions imported`, {
        description: `${result.created} new rows · ${formatNumber(result.social_sessions)} from social`,
      });
      void queryClient.invalidateQueries({ queryKey: ['growth', 'traffic'] });
      void queryClient.invalidateQueries({ queryKey: ['growth', 'insights'] });
      void queryClient.invalidateQueries({ queryKey: ['growth', 'report'] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  /** Drop a recommended card into the builder and draft it immediately. */
  const applyCard = (card: GrowthNextCard) => {
    setKind(card.kind);
    setMetric(card.metric ?? AUTO);
    setCountry(card.country ?? AUTO);
    setPlayer(AUTO);
    setTeamA(AUTO);
    setTeamB(AUTO);
    requestSuggest({
      kind: card.kind,
      metric: card.metric ?? undefined,
      country: card.country ?? undefined,
      player: undefined,
      teams: undefined,
    });
  };

  // Auto-pick the first card once the season list is in, so the page is never
  // an empty form staring back at the user.
  useEffect(() => {
    if (!bootstrapped.current && activeSeason && meta.data) {
      bootstrapped.current = true;
      requestSuggest();
    }
  }, [activeSeason, meta.data, requestSuggest]);

  useEffect(() => {
    if (spec) requestPreview({ cardSpec: spec, cardFormat: format });
  }, [spec, format, requestPreview]);

  useEffect(() => {
    if (spec) {
      requestCaptions({ cardSpec: spec, utmCampaign: selectedCampaign?.utm_campaign || 'organic-growth' });
    }
  }, [spec, selectedCampaign, requestCaptions]);

  useEffect(() => {
    if (!preview.data) return;
    const url = URL.createObjectURL(preview.data);
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [preview.data]);

  const drafts = captions.data?.drafts ?? [];
  const visibleDrafts = drafts.filter(
    (draft) => draft.platform === captionPlatform && draft.locale === captionLocale,
  );

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to the clipboard');
    } catch {
      toast.error('The browser blocked clipboard access');
    }
  };

  const download = () => {
    if (!imageUrl || !spec) return;
    const anchor = document.createElement('a');
    anchor.href = imageUrl;
    anchor.download = `catchandstats-${spec.kind}-${format}.png`;
    anchor.click();
  };

  if (meta.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-9 w-56" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (meta.isError || !meta.data) {
    return (
      <EmptyState
        title="The growth studio could not load"
        description="Is the Django API running? Check the backend window and retry."
        action={<Button onClick={() => void meta.refetch()}>Retry</Button>}
      />
    );
  }

  const data = meta.data;
  const platforms = data.platforms;
  const kindLabels = new Map(data.kinds);
  const metricLabels = new Map(data.metrics.map((row) => [row.key, row.label]));
  const platformLabels = new Map(data.log_platforms ?? data.platforms);
  const trendFor = (platformName: string) => report.data?.trend.find((row) => row.platform === platformName);
  const localeNames: Record<string, string> = {
    en: 'English',
    el: 'Ελληνικά',
    tr: 'Türkçe',
    sr: 'Srpski',
    lt: 'Lietuvių',
  };

  return (
    <div className="space-y-4">
      <PageHeader
        title="Growth studio"
        description="Turn the season's numbers into a card, a caption in five languages, and next week's calendar."
        actions={
          <div className="flex items-center gap-2">
            <Select value={activeSeason} onValueChange={setSeason}>
              <SelectTrigger className="w-40" aria-label="Season">
                <SelectValue placeholder="Season" />
              </SelectTrigger>
              <SelectContent>
                {data.seasons.map((row) => (
                  <SelectItem key={row.id} value={String(row.id)}>
                    {row.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={() => requestSuggest()} disabled={suggest.isPending || !activeSeason}>
              {suggest.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
              Draft a card
            </Button>
          </div>
        }
      />

      {data.warning && (
        <Alert variant="info" title="Data source note">
          {data.warning}
        </Alert>
      )}

      {dataWarning && (
        <Alert variant="destructive" title="These numbers are cached, not live">
          {dataWarning}
          {stale ? ' Cards built now still work; refresh once the API is back.' : ''}
        </Alert>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>1. Pick the story</CardTitle>
            <CardDescription>
              The site's own metrics — consistency, home-court swing, fantasy ceiling — not another box score.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Card type">
                <Select value={kind} onValueChange={setKind}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {data.kinds.map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <Field label="Market">
                <Select value={country} onValueChange={setCountry}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={AUTO}>All markets</SelectItem>
                    {Object.entries(data.country_labels).map(([code, label]) => (
                      <SelectItem key={code} value={code}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>

            {kind === 'matchup' ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Home team">
                  <Select value={teamA} onValueChange={setTeamA}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={AUTO}>Auto (Greece vs Türkiye)</SelectItem>
                      {(players.data?.teams ?? []).map((team) => (
                        <SelectItem key={team} value={team}>
                          {team}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Away team">
                  <Select value={teamB} onValueChange={setTeamB}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={AUTO}>Auto</SelectItem>
                      {(players.data?.teams ?? []).map((team) => (
                        <SelectItem key={team} value={team}>
                          {team}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Metric" hint="Leaves the pick to the daily rotation.">
                  <Select value={metric} onValueChange={setMetric}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={AUTO}>Auto (daily rotation)</SelectItem>
                      {data.metrics.map((row) => (
                        <SelectItem key={row.key} value={row.key}>
                          {row.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Player" hint="Optional — auto-picks the leader.">
                  <Select value={player} onValueChange={setPlayer}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={AUTO}>Auto (leader in the metric)</SelectItem>
                      {(players.data?.results ?? []).map((row) => (
                        <SelectItem key={row.id} value={String(row.id)}>
                          {row.name} · {row.team}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Format">
                <Select value={format} onValueChange={setFormat}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {data.formats.map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Attach to campaign" hint="Used for the calendar and attribution.">
                <Select value={activeCampaignId} onValueChange={setCampaignId}>
                  <SelectTrigger>
                    <SelectValue placeholder="No campaign" />
                  </SelectTrigger>
                  <SelectContent>
                    {(campaigns.data?.results ?? []).map((row) => (
                      <SelectItem key={row.id} value={String(row.id)}>
                        {row.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle>2. Preview</CardTitle>
              <CardDescription>
                {format} · {data.sizes[format]?.[0]}×{data.sizes[format]?.[1]}
              </CardDescription>
            </div>
            {spec && (
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" onClick={download} disabled={!imageUrl}>
                  <Download />
                  PNG
                </Button>
                <Button size="sm" onClick={() => saveCard.mutate()} disabled={saveCard.isPending || !spec}>
                  {saveCard.isPending ? <Loader2 className="animate-spin" /> : <Save />}
                  Save
                </Button>
              </div>
            )}
          </CardHeader>
          <CardContent>
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={spec ? `Card: ${spec.title}` : 'Generated card'}
                className="w-full rounded-field border border-border"
              />
            ) : (
              <div className="flex aspect-video items-center justify-center rounded-field border border-dashed border-border bg-surface-alt text-sm text-muted-foreground">
                {preview.isPending ? <Loader2 className="size-5 animate-spin" /> : 'Draft a card to see it here'}
              </div>
            )}
            {spec?.headline && (
              <p className="mt-3 text-sm text-muted-foreground">
                <span className="font-semibold text-foreground">{spec.headline}</span> {spec.headline_label}
                {spec.headline_note ? ` · ${spec.headline_note}` : ''}
              </p>
            )}
            {fetchedAt && (
              <p className="mt-2 text-xs text-muted-foreground">
                Numbers fetched {formatDate(fetchedAt)}
                {stale ? ' (served from the cache)' : ''}
              </p>
            )}
            {link && (
              <div className="mt-3 flex items-center justify-between gap-2 rounded-field bg-surface-alt p-2.5">
                <code className="truncate text-xs text-muted-foreground">{link}</code>
                <Button variant="ghost" size="sm" onClick={() => void copy(link)}>
                  <Copy />
                  Link
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader className="flex-row items-start justify-between space-y-0">
            <div>
              <CardTitle>3. Captions</CardTitle>
              <CardDescription>
                English and Greek are full drafts; Turkish, Serbian and Lithuanian get a native hook around the
                English body.
              </CardDescription>
            </div>
            <Button
              variant="secondary"
              size="sm"
              disabled={!visibleDrafts[0]}
              onClick={() => visibleDrafts[0] && copy(visibleDrafts[0].text)}
            >
              <Copy />
              Copy
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <Tabs value={captionPlatform} onValueChange={setCaptionPlatform}>
              <TabsList className="flex-wrap">
                {platforms.map(([value, label]) => (
                  <TabsTrigger key={value} value={value}>
                    {label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <Tabs value={captionLocale} onValueChange={setCaptionLocale}>
              <TabsList className="flex-wrap">
                {data.locales.map((locale) => (
                  <TabsTrigger key={locale} value={locale}>
                    {localeNames[locale] ?? locale.toUpperCase()}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>

            {visibleDrafts.length === 0 ? (
              <div className="rounded-field border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                {captions.isPending ? 'Writing drafts…' : 'Draft a card to get captions.'}
              </div>
            ) : (
              visibleDrafts.map((draft: CaptionDraft) => (
                <div key={`${draft.platform}-${draft.locale}`} className="space-y-2">
                  {draft.title && (
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Title</p>
                      <Button variant="ghost" size="sm" onClick={() => copy(draft.title)}>
                        <Copy />
                        Copy title
                      </Button>
                    </div>
                  )}
                  {draft.title && (
                    <div className="rounded-field bg-surface-alt p-3 text-sm font-medium">{draft.title}</div>
                  )}
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Body</p>
                    <span
                      className={
                        draft.within_limit ? 'text-xs text-muted-foreground' : 'text-xs font-semibold text-destructive'
                      }
                    >
                      {draft.length}/{draft.limit}
                    </span>
                  </div>
                  <div className="max-h-72 overflow-auto rounded-field bg-surface-alt p-3 text-sm whitespace-pre-wrap">
                    {draft.text}
                  </div>
                  {draft.localisation === 'hook' && (
                    <p className="text-xs text-muted-foreground">
                      Local hook + English body. Translate the body by hand if the post is worth it.
                    </p>
                  )}
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>4. Next week</CardTitle>
            <CardDescription>
              Eight posts, Monday to Sunday, written straight into the calendar and the to-do list.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Field label="Round label">
              <Input
                value={roundLabel}
                onChange={(event) => setRoundLabel(event.target.value)}
                placeholder="Round 7"
              />
            </Field>
            <Field label="Week of" hint="Snaps to the Monday of that week.">
              <Input type="date" value={weekStart} onChange={(event) => setWeekStart(event.target.value)} />
            </Field>
            <Button
              className="w-full"
              onClick={() => seedPlan.mutate()}
              disabled={seedPlan.isPending || !activeCampaignId}
            >
              {seedPlan.isPending ? <Loader2 className="animate-spin" /> : <CalendarPlus />}
              Fill the calendar
            </Button>
            {!activeCampaignId && <p className="text-xs text-muted-foreground">Choose a campaign above first.</p>}

            {planResult && (
              <Alert
                variant={planResult.missing_channels.length ? 'destructive' : 'success'}
                title={`${planResult.created} posts added, ${planResult.skipped} already there`}
              >
                {planResult.missing_channels.length
                  ? `Create a channel for: ${planResult.missing_channels.join(', ')} — those posts have no channel yet.`
                  : `Week of ${formatDate(planResult.week_start)} · ${planResult.tasks} tasks created.`}
                {planResult.warning ? ` ${planResult.warning}` : ''}
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle>5. What worked</CardTitle>
            <CardDescription>
              Clicks and click rate per platform, card type and metric. Follower counts do not pay for the
              servers.
            </CardDescription>
          </div>
          <Select value={String(reportDays)} onValueChange={(value) => setReportDays(Number(value))}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatBox
              label="Posts"
              value={formatNumber(report.data?.totals.posts ?? 0)}
              hint={`${formatNumber(report.data?.previous_totals.posts ?? 0)} in the window before`}
            />
            <StatBox label="Impressions" value={formatNumber(report.data?.totals.impressions ?? 0)} />
            <StatBox
              label="Clicks"
              value={formatNumber(report.data?.totals.clicks ?? 0)}
              hint={`${formatNumber(report.data?.previous_totals.clicks ?? 0)} in the window before`}
            />
            <StatBox
              label="Click rate"
              value={rate(report.data?.totals.click_rate ?? null)}
              hint={`was ${rate(report.data?.previous_totals.click_rate ?? null)}`}
            />
          </div>

          {report.data?.by_platform.length ? (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Platform</TableHead>
                    <TableHead className="text-right">Posts</TableHead>
                    <TableHead className="text-right">Impressions</TableHead>
                    <TableHead className="text-right">Clicks</TableHead>
                    <TableHead className="text-right">Click rate</TableHead>
                    <TableHead className="text-right">vs before</TableHead>
                    <TableHead className="text-right">Engagement</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {report.data.by_platform.map((row) => (
                    <TableRow key={row.platform}>
                      <TableCell className="font-medium">{row.label}</TableCell>
                      <TableCell className="text-right">{formatNumber(row.posts)}</TableCell>
                      <TableCell className="text-right">{formatNumber(row.impressions)}</TableCell>
                      <TableCell className="text-right">{formatNumber(row.clicks)}</TableCell>
                      <TableCell className="text-right">{rate(row.click_rate)}</TableCell>
                      <TableCell className="text-right">
                        <TrendDelta row={trendFor(row.platform ?? '')} />
                      </TableCell>
                      <TableCell className="text-right">{rate(row.engagement_rate)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No posts logged yet. Log the first one below and the table fills itself.
            </p>
          )}

          <div className="grid gap-4 border-t border-border pt-4 lg:grid-cols-2">
            <div className="space-y-2">
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">By card type</p>
              <BreakdownTable rows={report.data?.by_kind ?? []} group="kind" />
            </div>
            <div className="space-y-2">
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">By metric</p>
              <BreakdownTable rows={report.data?.by_metric ?? []} group="metric" />
            </div>
          </div>

          <div className="grid gap-3 border-t border-border pt-4 sm:grid-cols-6">
            <Field label="Platform">
              <Select value={logPlatform} onValueChange={setLogPlatform}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(data.log_platforms ?? platforms).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Date">
              <Input type="date" value={logDate} onChange={(event) => setLogDate(event.target.value)} />
            </Field>
            <Field label="Impressions">
              <Input
                inputMode="numeric"
                value={logImpressions}
                onChange={(event) => setLogImpressions(event.target.value)}
                placeholder="12000"
              />
            </Field>
            <Field label="Engagements">
              <Input
                inputMode="numeric"
                value={logEngagements}
                onChange={(event) => setLogEngagements(event.target.value)}
                placeholder="480"
              />
            </Field>
            <Field label="Clicks">
              <Input
                inputMode="numeric"
                value={logClicks}
                onChange={(event) => setLogClicks(event.target.value)}
                placeholder="210"
              />
            </Field>
            <Field label="Link">
              <Input value={logUrl} onChange={(event) => setLogUrl(event.target.value)} placeholder="https://…" />
            </Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Card type" hint="Optional — feeds the by-type ranking above.">
              <Select value={logKind} onValueChange={setLogKind}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Not recorded</SelectItem>
                  {data.kinds.map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Metric" hint="Optional — feeds the by-metric ranking above.">
              <Select value={logMetric} onValueChange={setLogMetric}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Not recorded</SelectItem>
                  {data.metrics.map((row) => (
                    <SelectItem key={row.key} value={row.key}>
                      {row.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
          <Button variant="secondary" onClick={() => logPost.mutate()} disabled={logPost.isPending}>
            {logPost.isPending ? <Loader2 className="animate-spin" /> : null}
            Log post
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row items-start justify-between space-y-0">
          <div>
            <CardTitle>6. Where the traffic came from</CardTitle>
            <CardDescription>
              GA4 sessions per source. Clicks without sessions is a broken link, not bad luck.
            </CardDescription>
          </div>
          {data.can_sync && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => syncTraffic.mutate(reportDays)}
              disabled={syncTraffic.isPending}
            >
              {syncTraffic.isPending ? <Loader2 className="animate-spin" /> : <RefreshCw />}
              Sync GA4
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {!data.ga4_configured && (
            <Alert variant="info" title="Google Analytics is not configured">
              Add the service-account JSON and the GA4 property ID in Settings → API keys. Once the
              integration works, “Sync GA4” fills this section and the traffic rules start firing.
            </Alert>
          )}

          {data.ga4_configured && traffic.data && traffic.data.summary.totals.sessions === 0 && (
            <Alert variant="info" title="No sessions imported yet">
              {data.can_sync
                ? `Press “Sync GA4” to import the last ${reportDays} days of sessions.`
                : 'Ask an administrator to run the sync, or run manage.py sync_google --organic on the server.'}
            </Alert>
          )}

          {traffic.data && traffic.data.summary.totals.sessions > 0 && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <StatBox
                  label="Sessions"
                  value={formatNumber(traffic.data.summary.totals.sessions)}
                  hint={`last ${traffic.data.days} days`}
                />
                <StatBox
                  label="From social"
                  value={formatNumber(traffic.data.summary.totals.social_sessions)}
                />
                <StatBox
                  label="Engaged"
                  value={formatNumber(traffic.data.summary.totals.engaged_sessions)}
                />
                <StatBox label="Page views" value={formatNumber(traffic.data.summary.totals.views)} />
              </div>

              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Source</TableHead>
                      <TableHead>Medium</TableHead>
                      <TableHead>Platform</TableHead>
                      <TableHead className="text-right">Sessions</TableHead>
                      <TableHead className="text-right">Engaged</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {traffic.data.summary.by_source.map((row) => (
                      <TableRow key={`${row.source}-${row.medium}`}>
                        <TableCell className="font-medium">{row.source}</TableCell>
                        <TableCell className="text-muted-foreground">{row.medium || '—'}</TableCell>
                        <TableCell>
                          {row.platform ? (platformLabels.get(row.platform) ?? row.platform) : '—'}
                        </TableCell>
                        <TableCell className="text-right">{formatNumber(row.sessions)}</TableCell>
                        <TableCell className="text-right">{rate(row.engagement_rate)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {traffic.data.last_synced_at && (
                <p className="text-xs text-muted-foreground">
                  Last synced {formatDate(traffic.data.last_synced_at)}
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>7. What to do next</CardTitle>
          <CardDescription>
            Rules over the same numbers: what is leaking, what is worth repeating, what to stop.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {insights.isPending && <Skeleton className="h-24" />}

          {insights.data?.insights.map((insight) => (
            <Alert key={insight.id} variant={SEVERITY_VARIANT[insight.severity]} title={insight.title}>
              <p>{insight.detail}</p>
              {insight.evidence.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {insight.evidence.map((line) => (
                    <li key={line}>· {line}</li>
                  ))}
                </ul>
              )}
            </Alert>
          ))}

          {insights.data && insights.data.insights.length === 0 && (
            <p className="text-sm text-muted-foreground">
              Nothing to flag yet. Log a few posts and this fills itself.
            </p>
          )}

          {(insights.data?.next_cards.length ?? 0) > 0 && (
            <div className="space-y-2 border-t border-border pt-4">
              <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                Build this next
              </p>
              {insights.data?.next_cards.map((card) => (
                <div
                  key={`${card.kind}-${card.metric ?? 'any'}`}
                  className="flex items-center justify-between gap-3 rounded-field bg-surface-alt p-3"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {kindLabels.get(card.kind) ?? card.kind}
                      {card.metric ? ` · ${metricLabels.get(card.metric) ?? card.metric}` : ''}
                    </p>
                    <p className="text-xs text-muted-foreground">{card.reason}</p>
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => applyCard(card)}>
                    <Wand2 />
                    Use
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
