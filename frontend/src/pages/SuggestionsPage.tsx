import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { PageHeader } from '@/components/PageHeader';
import { fetchList, qk } from '@/lib/data';
import { formatDateTime } from '@/lib/format';
import type { Campaign, Suggestion } from '@/lib/types';
import { Badge } from '@/ui/badge';
import { EmptyState } from '@/ui/empty-state';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';
import { SuggestionKindBadge } from '@/ui/status-badge';

const PAGE_SIZE = 20;

export default function SuggestionsPage() {
  const [page, setPage] = useState(1);
  const [kind, setKind] = useState('all');
  const [accepted, setAccepted] = useState('all');
  const [campaignFilter, setCampaignFilter] = useState('all');

  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 200 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 200, ordering: 'name' }),
  });
  const campaignNames = useMemo(
    () => new Map((campaigns.data?.results ?? []).map((c) => [c.id, c.name])),
    [campaigns.data],
  );

  const params = useMemo(
    () => ({
      page,
      page_size: PAGE_SIZE,
      ordering: '-created_at',
      kind: kind === 'all' ? undefined : kind,
      accepted: accepted === 'all' ? undefined : accepted === 'accepted',
      campaign: campaignFilter === 'all' ? undefined : Number(campaignFilter),
    }),
    [page, kind, accepted, campaignFilter],
  );

  const list = useQuery({
    queryKey: qk.suggestions(params),
    queryFn: () => fetchList<Suggestion>('/suggestions/', params),
    placeholderData: keepPreviousData,
  });

  const rows = list.data?.results ?? [];
  const hasFilters = kind !== 'all' || accepted !== 'all' || campaignFilter !== 'all';

  return (
    <div>
      <PageHeader
        title="Suggestions"
        description="Rule-based and AI-generated next steps across campaigns. Generate them from a campaign's page."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Select value={kind} onValueChange={(v) => { setKind(v); setPage(1); }}>
          <SelectTrigger className="w-36" aria-label="Filter by kind">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All kinds</SelectItem>
            <SelectItem value="rule">Rules</SelectItem>
            <SelectItem value="ai">AI</SelectItem>
          </SelectContent>
        </Select>
        <Select value={accepted} onValueChange={(v) => { setAccepted(v); setPage(1); }}>
          <SelectTrigger className="w-40" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Any status</SelectItem>
            <SelectItem value="accepted">Accepted</SelectItem>
            <SelectItem value="open">Not accepted</SelectItem>
          </SelectContent>
        </Select>
        <Select value={campaignFilter} onValueChange={(v) => { setCampaignFilter(v); setPage(1); }}>
          <SelectTrigger className="w-48" aria-label="Filter by campaign">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All campaigns</SelectItem>
            {(campaigns.data?.results ?? []).map((c) => (
              <SelectItem key={c.id} value={String(c.id)}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {list.isLoading ? (
        <div className="grid gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title={hasFilters ? 'No suggestions match your filters' : 'No suggestions yet'}
          description={
            hasFilters
              ? 'Try clearing a filter.'
              : 'Open a campaign and use "Generate rules" — it works without any API key.'
          }
        />
      ) : (
        <>
          <ul className="grid gap-3">
            {rows.map((s) => (
              <li key={s.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <SuggestionKindBadge kind={s.kind} />
                  <strong className="text-sm font-semibold">{s.title}</strong>
                  {s.accepted && <Badge variant="success">Accepted</Badge>}
                  <span className="ml-auto text-xs text-muted-foreground">{formatDateTime(s.created_at)}</span>
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{s.text}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Campaign:{' '}
                  <Link to={`/campaigns/${s.campaign}`} className="font-medium text-primary hover:underline">
                    {campaignNames.get(s.campaign) ?? `#${s.campaign}`}
                  </Link>
                </p>
                {s.input_snapshot && Object.keys(s.input_snapshot).length > 0 && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                      Why this suggestion?
                    </summary>
                    <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-muted p-3 text-xs">
                      {JSON.stringify(s.input_snapshot, null, 2)}
                    </pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
