import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { SuggestionCard } from '@/components/SuggestionCard';
import { fetchList, qk } from '@/lib/data';
import type { Campaign, Suggestion } from '@/lib/types';
import { EmptyState } from '@/ui/empty-state';
import { Pagination } from '@/ui/pagination';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import { Skeleton } from '@/ui/skeleton';

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
              <li key={s.id}>
                <SuggestionCard suggestion={s} campaignName={campaignNames.get(s.campaign)} />
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={PAGE_SIZE} count={list.data?.count ?? 0} onPageChange={setPage} />
        </>
      )}
    </div>
  );
}
