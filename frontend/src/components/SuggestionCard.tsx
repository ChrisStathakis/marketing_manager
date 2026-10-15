import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCheck, ListPlus, RotateCcw, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import { formatDateTime } from '@/lib/format';
import type { Suggestion } from '@/lib/types';
import { Badge } from '@/ui/badge';
import { Button } from '@/ui/button';
import { SuggestionKindBadge } from '@/ui/status-badge';

interface SuggestionCardProps {
  suggestion: Suggestion;
  campaignName?: string;
  /** When true the campaign name links to its detail page. */
  linkCampaign?: boolean;
}

/**
 * One suggestion with its workflow actions:
 * accept -> task on the calendar, dismiss -> handled, reopen -> back to open.
 */
export function SuggestionCard({ suggestion, campaignName, linkCampaign = true }: SuggestionCardProps) {
  const qc = useQueryClient();

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ['suggestions'] });
    qc.invalidateQueries({ queryKey: ['tasks'] });
  };

  const accept = useMutation({
    mutationFn: async () => (await api.post(`/suggestions/${suggestion.id}/accept/`)).data,
    onSuccess: () => {
      invalidate();
      toast.success('Accepted — task added to the calendar');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const dismiss = useMutation({
    mutationFn: async () => (await api.patch(`/suggestions/${suggestion.id}/`, { accepted: true })).data,
    onSuccess: () => {
      invalidate();
      toast.success('Suggestion dismissed');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const reopen = useMutation({
    mutationFn: async () => (await api.post(`/suggestions/${suggestion.id}/reopen/`)).data,
    onSuccess: () => {
      invalidate();
      toast.success('Suggestion reopened');
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const pending = accept.isPending || dismiss.isPending || reopen.isPending;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <SuggestionKindBadge kind={suggestion.kind} />
        <strong className="text-sm font-semibold">{suggestion.title}</strong>
        {suggestion.task ? (
          <Badge variant={suggestion.task.done ? 'success' : 'default'}>
            <CheckCheck className="size-3" />
            Task {suggestion.task.done ? 'done' : 'on calendar'}
          </Badge>
        ) : (
          suggestion.accepted && <Badge variant="secondary">Dismissed</Badge>
        )}
        <span className="ml-auto text-xs text-muted-foreground">{formatDateTime(suggestion.created_at)}</span>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{suggestion.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        {campaignName && (
          <span className="text-xs text-muted-foreground">
            Campaign:{' '}
            {linkCampaign ? (
              <Link to={`/campaigns/${suggestion.campaign}`} className="font-medium text-primary hover:underline">
                {campaignName}
              </Link>
            ) : (
              <span className="font-medium">{campaignName}</span>
            )}
          </span>
        )}
        <span className="flex-1" />
        {!suggestion.accepted && (
          <>
            <Button size="sm" onClick={() => accept.mutate()} disabled={pending}>
              <ListPlus /> Accept → task
            </Button>
            <Button size="sm" variant="ghost" onClick={() => dismiss.mutate()} disabled={pending}>
              Dismiss
            </Button>
          </>
        )}
        {suggestion.accepted && (
          <Button size="sm" variant="outline" onClick={() => reopen.mutate()} disabled={pending}>
            <RotateCcw /> Reopen
          </Button>
        )}
      </div>
      {suggestion.input_snapshot && Object.keys(suggestion.input_snapshot).length > 0 && (
        <details className="mt-2">
          <summary className="flex cursor-pointer items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <Sparkles className="size-3" /> Why this suggestion?
          </summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-muted p-3 text-xs">
            {JSON.stringify(suggestion.input_snapshot, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
