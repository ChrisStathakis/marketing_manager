import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowDown,
  ArrowUp,
  CalendarPlus,
  Copy,
  Download,
  Images,
  Loader2,
  Plus,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { downloadFile, fetchList, fetchOne, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { formatDate, formatDateTime, formatNumber, toDateInputValue } from '@/lib/format';
import type {
  Campaign,
  CardSet,
  GrowthMeta,
  Playbook,
  PlaybookPreview,
  PlaybookRunResult,
  PlaybookSlot,
} from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { EmptyState } from '@/ui/empty-state';
import { Field } from '@/ui/field';
import { Input, Textarea } from '@/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

const NONE = 'none';

function blankSlot(order: number): PlaybookSlot {
  return {
    order,
    day_offset: 0,
    time: '21:00',
    platform: 'instagram',
    format: 'post',
    content_kind: '',
    locales: [],
    title_template: 'New post — {round}',
    brief: '',
    utm_content_template: '',
    asset_required: false,
    paid_budget: '0',
    is_task_only: false,
    notes: '',
  };
}

function clonePlaybook(playbook: Playbook): Playbook {
  return {
    ...playbook,
    default_locales: [...playbook.default_locales],
    default_platforms: [...playbook.default_platforms],
    slots: playbook.slots.map((slot) => ({
      ...slot,
      locales: [...(slot.locales ?? [])],
    })),
  };
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 rounded border-border"
      />
      {label}
    </label>
  );
}

export default function PlaybooksPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Playbook | null>(null);
  const [startDate, setStartDate] = useState(() => toDateInputValue(new Date()));
  const [roundLabel, setRoundLabel] = useState('');
  const [campaignId, setCampaignId] = useState('');
  const [utmCampaign, setUtmCampaign] = useState('');
  const [landingPath, setLandingPath] = useState('');
  const [locales, setLocales] = useState<string[]>(['el', 'en']);
  const [platforms, setPlatforms] = useState<string[]>(['instagram', 'x', 'tiktok', 'reddit']);
  const [createTargets, setCreateTargets] = useState(true);
  const [targets, setTargets] = useState<Record<string, string>>({
    impressions: '150000',
    saves: '400',
    shares: '250',
    profile_visits: '800',
    clicks: '900',
    signups: '60',
    upvote_ratio: '0.9',
    search_clicks: '250',
    search_impressions: '5000',
    search_ctr: '0.05',
  });
  const [skipPast, setSkipPast] = useState(false);
  const [preview, setPreview] = useState<PlaybookPreview | null>(null);
  const [runResult, setRunResult] = useState<PlaybookRunResult | null>(null);
  const [cardSet, setCardSet] = useState<CardSet | null>(null);

  const meta = useQuery({
    queryKey: qk.growthMeta,
    queryFn: () => fetchOne<GrowthMeta>('/growth/meta/'),
    staleTime: 10 * 60 * 1000,
  });
  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 100 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 100, ordering: '-created_at' }),
  });
  const playbooks = useQuery({
    queryKey: ['playbooks'],
    queryFn: () => fetchList<Playbook>('/playbooks/', { page_size: 100, ordering: 'name' }),
  });

  const activeId = selectedId ?? playbooks.data?.results[0]?.id ?? null;
  const selected = useMemo(
    () => playbooks.data?.results.find((row) => row.id === activeId) ?? null,
    [playbooks.data, activeId],
  );

  useEffect(() => {
    if (selected) {
      setDraft(clonePlaybook(selected));
      setLocales(selected.default_locales?.length ? selected.default_locales : ['el', 'en']);
      setPlatforms(selected.default_platforms ?? []);
      setPreview(null);
    }
  }, [selected]);

  const metaPlatforms = meta.data?.playbook_platforms ?? [];
  const formats = meta.data?.content_formats ?? [];
  const kindOptions = meta.data?.kinds ?? [];
  const localeOptions = meta.data?.content_locales ?? [];
  const kpiMetrics = meta.data?.kpi_metrics ?? [];

  const persistDraft = async (payload: Playbook) => {
    const body = {
      name: payload.name,
      description: payload.description,
      default_locales: payload.default_locales,
      default_platforms: payload.default_platforms,
      slots: payload.slots.map((slot, index) => ({
        order: index,
        day_offset: Number(slot.day_offset) || 0,
        time: slot.time,
        platform: slot.platform,
        format: slot.format,
        content_kind: slot.content_kind || '',
        locales: slot.locales,
        title_template: slot.title_template,
        brief: slot.brief,
        utm_content_template: slot.utm_content_template,
        asset_required: slot.asset_required,
        paid_budget: slot.paid_budget || '0',
        is_task_only: slot.is_task_only,
        notes: slot.notes,
      })),
    };
    const { data } = await api.put<Playbook>(`/playbooks/${payload.id}/`, body);
    return data;
  };

  const save = useMutation({
    mutationFn: persistDraft,
    onSuccess: (updated) => {
      toast.success('Playbook saved');
      setDraft(clonePlaybook(updated));
      void queryClient.invalidateQueries({ queryKey: ['playbooks'] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const createPlaybook = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<Playbook>('/playbooks/', {
        name: 'New content playbook',
        description: 'A reusable series. Give each slot a day offset; a run turns it into dates.',
        default_locales: ['en'],
        default_platforms: ['instagram'],
        slots: [blankSlot(0)],
      });
      return data;
    },
    onSuccess: (created) => {
      setSelectedId(created.id);
      void queryClient.invalidateQueries({ queryKey: ['playbooks'] });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const duplicate = useMutation({
    mutationFn: async () => {
      if (!selected) throw new Error('Choose a playbook first.');
      const { data } = await api.post<Playbook>(`/playbooks/${selected.id}/duplicate/`, {
        name: `${selected.name} — copy`,
      });
      return data;
    },
    onSuccess: (created) => {
      setSelectedId(created.id);
      void queryClient.invalidateQueries({ queryKey: ['playbooks'] });
      toast.success('Playbook duplicated');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const runPreview = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error('Choose a playbook first.');
      await persistDraft(draft);
      const { data } = await api.post<PlaybookPreview>(`/playbooks/${draft.id}/preview/`, {
        start_date: startDate,
        round_label: roundLabel,
        locales,
        platforms,
        skip_past: skipPast,
        utm_campaign: utmCampaign || undefined,
        landing_path: landingPath || undefined,
      });
      return data;
    },
    onSuccess: setPreview,
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const run = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error('Choose a playbook first.');
      await persistDraft(draft);
      const { data } = await api.post<PlaybookRunResult>(`/playbooks/${draft.id}/run/`, {
        start_date: startDate,
        round_label: roundLabel,
        locales,
        platforms,
        skip_past: skipPast,
        create_targets: createTargets,
        kpi_targets: Object.entries(targets)
          .filter(([, value]) => value !== '')
          .map(([metric, target]) => ({ metric, target: Number(target) })),
        utm_campaign: utmCampaign || undefined,
        landing_path: landingPath || undefined,
      });
      return data;
    },
    onSuccess: (result) => {
      setRunResult(result);
      setCampaignId(String(result.campaign.id));
      toast.success(`${result.created} posts scheduled`, {
        description: `${result.campaign.name} · ${formatDate(result.campaign.start_date)}`,
      });
      void queryClient.invalidateQueries({ queryKey: qk.content() });
      void queryClient.invalidateQueries({ queryKey: qk.tasks() });
      void queryClient.invalidateQueries({ queryKey: qk.campaigns({ page_size: 100 }) });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const buildSet = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<CardSet>('/card-sets/', {
        campaign: campaignId ? Number(campaignId) : null,
        season: meta.data?.default_season?.id,
        format: 'instagram',
        top_n: 8,
        compare_previous: true,
        include_table: false,
        include_cta: true,
        title: roundLabel ? `Top 8 after ${roundLabel}` : undefined,
      });
      return data;
    },
    onSuccess: (set) => {
      setCardSet(set);
      toast.success(`${set.slides.length} slides rendered`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const updateSlot = (index: number, patch: Partial<PlaybookSlot>) => {
    setDraft((current) => {
      if (!current) return current;
      const slots = current.slots.map((slot, slotIndex) =>
        slotIndex === index ? { ...slot, ...patch } : slot,
      );
      return { ...current, slots };
    });
  };

  const moveSlot = (index: number, direction: -1 | 1) => {
    setDraft((current) => {
      if (!current) return current;
      const target = index + direction;
      if (target < 0 || target >= current.slots.length) return current;
      const slots = [...current.slots];
      [slots[index], slots[target]] = [slots[target], slots[index]];
      return { ...current, slots: slots.map((slot, order) => ({ ...slot, order })) };
    });
  };

  const deleteSlot = (index: number) => {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        slots: current.slots.filter((_, slotIndex) => slotIndex !== index).map((slot, order) => ({ ...slot, order })),
      };
    });
  };

  if (meta.isError || playbooks.isError) {
    return (
      <EmptyState
        title="Playbooks could not load"
        description="Check the API and try again."
        action={<Button onClick={() => void playbooks.refetch()}>Retry</Button>}
      />
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Playbooks"
        description="A reusable, date-free content series. Pick a start date and every slot becomes a dated post on a new campaign."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => createPlaybook.mutate()} disabled={createPlaybook.isPending}>
              <Plus />
              New
            </Button>
            <Button variant="secondary" onClick={() => duplicate.mutate()} disabled={!selected || duplicate.isPending}>
              <Copy />
              Duplicate
            </Button>
          </div>
        }
      />

      {meta.data?.warning && (
        <Alert variant="info" title="Data source note">
          {meta.data.warning}
        </Alert>
      )}

      <div className="grid gap-4 xl:grid-cols-[260px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Library</CardTitle>
            <CardDescription>{playbooks.data?.count ?? 0} playbooks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-1">
            {playbooks.isPending && <Skeleton className="h-24" />}
            {playbooks.data?.results.map((row) => (
              <button
                key={row.id}
                type="button"
                onClick={() => setSelectedId(row.id)}
                className={`w-full rounded-field px-3 py-2 text-left text-sm transition ${
                  row.id === activeId ? 'bg-primary/10 font-medium text-primary' : 'hover:bg-surface-alt'
                }`}
              >
                <span className="block truncate">{row.name}</span>
                <span className="text-xs text-muted-foreground">{row.slot_count} slots</span>
              </button>
            ))}
          </CardContent>
        </Card>

        {draft ? (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Template</CardTitle>
                <CardDescription>
                  Day offsets, not dates. Reorder with the arrows; the run recalculates every publish time.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Name">
                    <Input
                      value={draft.name}
                      onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                    />
                  </Field>
                  <Field label="Default platforms" hint="Comma-separated.">
                    <Input
                      value={draft.default_platforms.join(', ')}
                      onChange={(event) =>
                        setDraft({
                          ...draft,
                          default_platforms: event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
                        })
                      }
                    />
                  </Field>
                </div>
                <Field label="Description">
                  <Textarea
                    rows={2}
                    value={draft.description}
                    onChange={(event) => setDraft({ ...draft, description: event.target.value })}
                  />
                </Field>

                <div className="space-y-3">
                  {draft.slots.map((slot, index) => (
                    <div key={`${slot.id ?? 'new'}-${index}`} className="rounded-field border border-border p-3">
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                          Slot {index + 1} · day +{slot.day_offset}
                        </p>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" onClick={() => moveSlot(index, -1)} disabled={index === 0}>
                            <ArrowUp />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => moveSlot(index, 1)}
                            disabled={index === draft.slots.length - 1}
                          >
                            <ArrowDown />
                          </Button>
                          <Button variant="ghost" size="icon" onClick={() => deleteSlot(index)}>
                            <Trash2 />
                          </Button>
                        </div>
                      </div>

                      <div className="grid gap-3 md:grid-cols-6">
                        <Field label="Day">
                          <Input
                            type="number"
                            min={0}
                            value={slot.day_offset}
                            onChange={(event) => updateSlot(index, { day_offset: Number(event.target.value) })}
                          />
                        </Field>
                        <Field label="Time">
                          <Input
                            type="time"
                            value={slot.time.slice(0, 5)}
                            onChange={(event) => updateSlot(index, { time: event.target.value })}
                          />
                        </Field>
                        <Field label="Platform">
                          <Select value={slot.platform} onValueChange={(value) => updateSlot(index, { platform: value })}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {metaPlatforms.map(([value, label]) => (
                                <SelectItem key={value} value={value}>
                                  {label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Field>
                        <Field label="Format">
                          <Select value={slot.format} onValueChange={(value) => updateSlot(index, { format: value })}>
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {formats.map(([value, label]) => (
                                <SelectItem key={value} value={value}>
                                  {label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Field>
                        <Field label="Card type">
                          <Select
                            value={slot.content_kind || NONE}
                            onValueChange={(value) =>
                              updateSlot(index, { content_kind: value === NONE ? '' : value })
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value={NONE}>None</SelectItem>
                              {kindOptions.map(([value, label]) => (
                                <SelectItem key={value} value={value}>
                                  {label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </Field>
                        <Field label="Paid budget">
                          <Input
                            type="number"
                            min={0}
                            step="0.01"
                            value={slot.paid_budget}
                            onChange={(event) => updateSlot(index, { paid_budget: event.target.value })}
                          />
                        </Field>
                      </div>

                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        <Field label="Title template" hint="Use {round}; add {locale} only if you want it in the title.">
                          <Input
                            value={slot.title_template}
                            onChange={(event) => updateSlot(index, { title_template: event.target.value })}
                          />
                        </Field>
                        <Field label="UTM content" hint="e.g. carousel_el. Empty falls back to format_locale.">
                          <Input
                            value={slot.utm_content_template}
                            onChange={(event) => updateSlot(index, { utm_content_template: event.target.value })}
                          />
                        </Field>
                      </div>
                      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_220px]">
                        <Field label="Brief">
                          <Textarea
                            rows={2}
                            value={slot.brief}
                            onChange={(event) => updateSlot(index, { brief: event.target.value })}
                          />
                        </Field>
                        <Field label="Locales" hint="Comma-separated; empty inherits the run.">
                          <Input
                            value={slot.locales.join(', ')}
                            onChange={(event) =>
                              updateSlot(index, {
                                locales: event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
                              })
                            }
                          />
                        </Field>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-4">
                        <Toggle
                          checked={slot.asset_required}
                          onChange={(checked) => updateSlot(index, { asset_required: checked })}
                          label="Asset required"
                        />
                        <Toggle
                          checked={slot.is_task_only}
                          onChange={(checked) => updateSlot(index, { is_task_only: checked })}
                          label="To-do only"
                        />
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        slots: [...draft.slots, blankSlot(draft.slots.length)],
                      })
                    }
                  >
                    <Plus />
                    Add slot
                  </Button>
                  <Button onClick={() => save.mutate(draft)} disabled={save.isPending}>
                    {save.isPending ? <Loader2 className="animate-spin" /> : <Save />}
                    Save template
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Run it</CardTitle>
                <CardDescription>
                  Every run creates a new campaign, scheduled posts, to-dos and KPI targets. Nothing posts itself.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <Field label="Start date">
                    <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
                  </Field>
                  <Field label="Round label">
                    <Input
                      value={roundLabel}
                      onChange={(event) => setRoundLabel(event.target.value)}
                      placeholder="Round 8"
                    />
                  </Field>
                  <Field label="Campaign for hero set" hint="Optional.">
                    <Select value={campaignId || NONE} onValueChange={(value) => setCampaignId(value === NONE ? '' : value)}>
                      <SelectTrigger>
                        <SelectValue placeholder="None" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value={NONE}>None</SelectItem>
                        {campaigns.data?.results.map((row) => (
                          <SelectItem key={row.id} value={String(row.id)}>
                            {row.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </Field>
                  <Field label="UTM campaign" hint="Leave empty to derive it from the playbook and round.">
                    <Input
                      value={utmCampaign}
                      onChange={(event) => setUtmCampaign(event.target.value)}
                      placeholder="auto: top8-round-8"
                    />
                  </Field>
                  <Field
                    label="Landing path"
                    hint="Optional. Gives campaign links (and Search Console) a real page instead of the homepage."
                  >
                    <Input
                      value={landingPath}
                      onChange={(event) => setLandingPath(event.target.value)}
                      placeholder="/team-advanced-stats"
                    />
                  </Field>
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Locales</p>
                    <div className="flex flex-wrap gap-3">
                      {localeOptions.map(([value, label]) => (
                        <Toggle
                          key={value}
                          checked={locales.includes(value)}
                          onChange={(checked) =>
                            setLocales((current) =>
                              checked ? [...current, value] : current.filter((item) => item !== value),
                            )
                          }
                          label={label}
                        />
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Platforms</p>
                    <div className="flex flex-wrap gap-3">
                      {metaPlatforms.map(([value, label]) => (
                        <Toggle
                          key={value}
                          checked={platforms.includes(value)}
                          onChange={(checked) =>
                            setPlatforms((current) =>
                              checked ? [...current, value] : current.filter((item) => item !== value),
                            )
                          }
                          label={label}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-4">
                  <Toggle checked={createTargets} onChange={setCreateTargets} label="Create KPI targets" />
                  <Toggle checked={skipPast} onChange={setSkipPast} label="Skip times already past" />
                </div>

                {createTargets && (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                      KPI targets for this run
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                      {kpiMetrics.map(([value, label]) => (
                        <Field key={value} label={label}>
                          <Input
                            type="number"
                            step={value === 'upvote_ratio' || value === 'search_ctr' ? '0.01' : '1'}
                            min={0}
                            value={targets[value] ?? ''}
                            onChange={(event) =>
                              setTargets((current) => ({ ...current, [value]: event.target.value }))
                            }
                          />
                        </Field>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => runPreview.mutate()}
                    disabled={runPreview.isPending}
                  >
                    {runPreview.isPending ? <Loader2 className="animate-spin" /> : <Sparkles />}
                    Preview schedule
                  </Button>
                  <Button onClick={() => run.mutate()} disabled={run.isPending}>
                    {run.isPending ? <Loader2 className="animate-spin" /> : <CalendarPlus />}
                    Run playbook
                  </Button>
                  <Button variant="secondary" onClick={() => buildSet.mutate()} disabled={buildSet.isPending}>
                    {buildSet.isPending ? <Loader2 className="animate-spin" /> : <Images />}
                    Build Top 8 carousel
                  </Button>
                </div>

                {preview && (
                  <div className="space-y-2">
                    <Alert
                      variant={preview.missing_channels.length ? 'destructive' : 'info'}
                      title={`${preview.count} posts · ${formatDate(preview.start_date)} → ${formatDate(preview.end_date)}`}
                    >
                      {preview.missing_channels.length
                        ? `Create channels for: ${preview.missing_channels.join(', ')}.`
                        : `${preview.by_platform.map((row) => `${row.label} ${row.count}`).join(' · ')}`}
                    </Alert>
                    <div className="max-h-80 overflow-auto rounded-field border border-border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Publish</TableHead>
                            <TableHead>Title</TableHead>
                            <TableHead>Platform</TableHead>
                            <TableHead>Locale</TableHead>
                            <TableHead>UTM content</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {preview.items.map((item, index) => (
                            <TableRow key={`${item.title}-${item.publish_at}-${index}`}>
                              <TableCell className="whitespace-nowrap text-xs">
                                {formatDateTime(item.publish_at)}
                              </TableCell>
                              <TableCell>
                                <span className="font-medium">{item.title}</span>
                                {item.is_task_only && (
                                  <span className="ml-2 text-xs text-muted-foreground">to-do only</span>
                                )}
                              </TableCell>
                              <TableCell>{item.platform_label}</TableCell>
                              <TableCell>{item.locale.toUpperCase()}</TableCell>
                              <TableCell className="font-mono text-xs">{item.utm_content}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                )}

                {runResult && (
                  <Alert variant="success" title={`Created ${runResult.campaign.name}`}>
                    {runResult.created} posts, {runResult.tasks} tasks, {runResult.targets_created} KPI targets,{' '}
                    {runResult.boosts_created} planned boosts.
                    {runResult.missing_channels.length
                      ? ` Missing channels: ${runResult.missing_channels.join(', ')}.`
                      : ''}
                  </Alert>
                )}
              </CardContent>
            </Card>

            {cardSet && (
              <Card>
                <CardHeader className="flex-row items-start justify-between space-y-0">
                  <div>
                    <CardTitle>Top 8 carousel</CardTitle>
                    <CardDescription>
                      {cardSet.slides.length} slides · {cardSet.format} · ready for a human to post.
                    </CardDescription>
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      void downloadFile(`/card-sets/${cardSet.id}/download/`, undefined, `card-set-${cardSet.id}.zip`)
                    }
                  >
                    <Download />
                    ZIP
                  </Button>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
                    {cardSet.slides.map((slide, index) => (
                      <div key={slide.id} className="space-y-1">
                        {slide.image_url ? (
                          <img
                            src={slide.image_url}
                            alt={slide.title}
                            className="w-full rounded-field border border-border"
                          />
                        ) : (
                          <div className="flex aspect-[4/5] items-center justify-center rounded-field bg-surface-alt text-xs text-muted-foreground">
                            Slide {index + 1}
                          </div>
                        )}
                        <p className="truncate text-xs text-muted-foreground">
                          {index + 1}. {slide.title}
                        </p>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        ) : (
          <EmptyState title="No playbook selected" description="Create one or pick one from the library." />
        )}
      </div>

      {draft && (
        <p className="text-xs text-muted-foreground">
          Template has {formatNumber(draft.slots.length)} slots. The seeded plan is{' '}
          <span className="font-medium">Top 8 launch — 14 days</span>.
        </p>
      )}
    </div>
  );
}
