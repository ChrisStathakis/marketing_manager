import type { CampaignStatus, ContentStatus } from '@/lib/types';
import { Badge, type BadgeVariant } from './badge';

const CAMPAIGN_VARIANT: Record<CampaignStatus, BadgeVariant> = {
  draft: 'secondary',
  planned: 'outline',
  active: 'success',
  paused: 'warning',
  completed: 'default',
};

const CONTENT_VARIANT: Record<ContentStatus, BadgeVariant> = {
  draft: 'secondary',
  scheduled: 'warning',
  published: 'success',
};

const label = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function CampaignStatusBadge({ status }: { status: CampaignStatus }) {
  return <Badge variant={CAMPAIGN_VARIANT[status] ?? 'secondary'}>{label(status)}</Badge>;
}

export function ContentStatusBadge({ status }: { status: ContentStatus }) {
  return <Badge variant={CONTENT_VARIANT[status] ?? 'secondary'}>{label(status)}</Badge>;
}

export function SuggestionKindBadge({ kind }: { kind: 'rule' | 'ai' }) {
  return <Badge variant={kind === 'ai' ? 'default' : 'secondary'}>{kind === 'ai' ? 'AI' : 'Rule'}</Badge>;
}
