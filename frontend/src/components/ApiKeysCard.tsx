import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Check, ChevronDown, ExternalLink, KeyRound, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { fetchOne, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import type { Integration } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Badge } from '@/ui/badge';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';
import { Skeleton } from '@/ui/skeleton';

/** Status + in-app documentation for every third-party API key the backend uses. */
export function ApiKeysCard() {
  const qc = useQueryClient();
  const integrations = useQuery({
    queryKey: qk.integrations,
    queryFn: () => fetchOne<Integration[]>('/integrations/'),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-primary" /> API keys
        </CardTitle>
        <CardDescription>
          Keys for services the backend calls. They live server-side only — encrypted at rest, never part of the
          browser bundle, and never shown again after saving.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        {integrations.isLoading ? (
          <Skeleton className="h-28" />
        ) : integrations.isError ? (
          <Alert variant="destructive" title="Could not load integrations">
            {getErrorMessage(integrations.error)}
          </Alert>
        ) : (
          (integrations.data ?? []).map((integration) => (
            <IntegrationRow
              key={integration.id}
              integration={integration}
              onChanged={() => qc.invalidateQueries({ queryKey: qk.integrations })}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function IntegrationRow({ integration, onChanged }: { integration: Integration; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [key, setKey] = useState('');
  const [confirmingRemove, setConfirmingRemove] = useState(false);

  const save = useMutation({
    mutationFn: () => api.put(`/integrations/${integration.id}/`, { key: key.trim() }),
    onSuccess: () => {
      onChanged();
      setEditing(false);
      setKey('');
      toast.success(`${integration.label} key saved`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: () => api.delete(`/integrations/${integration.id}/`),
    onSuccess: () => {
      onChanged();
      setConfirmingRemove(false);
      toast.success(`${integration.label} key removed`);
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const trimmed = key.trim();
  const tooShort = trimmed.length < 16;
  const suspiciousPrefix = trimmed !== '' && !trimmed.startsWith('sk-');

  return (
    <div className="rounded-field border border-border bg-card/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-bold tracking-tight">{integration.label}</p>
            <StatusBadge integration={integration} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{integration.summary}</p>
          <SourceLine integration={integration} />
        </div>
        {!editing && (
          <div className="flex shrink-0 gap-2">
            <Button
              size="sm"
              variant={integration.configured ? 'outline' : 'default'}
              onClick={() => setEditing(true)}
            >
              {integration.stored ? 'Replace key' : 'Set key'}
            </Button>
            {integration.stored && (
              <Button size="sm" variant="outline" onClick={() => setConfirmingRemove(true)}>
                Remove
              </Button>
            )}
          </div>
        )}
      </div>

      {integration.stored_unreadable && (
        <Alert variant="destructive" className="mt-3" title="Saved key can't be decrypted">
          This usually means DJANGO_SECRET_KEY changed after the key was saved. Remove it and save the key again.
        </Alert>
      )}

      {editing && (
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
          <Field
            label={integration.stored ? `Replace ${integration.label} key` : `Add ${integration.label} key`}
            htmlFor={`integration-${integration.id}`}
            hint={
              suspiciousPrefix
                ? 'Expected a key starting with "sk-" — double-check the value.'
                : 'Minimum 16 characters. Sent once — never displayed again.'
            }
            className="min-w-0 flex-1"
          >
            <Input
              id={`integration-${integration.id}`}
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder={integration.stored ? 'New key value' : 'Paste the key'}
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
          </Field>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending || tooShort}>
              {save.isPending ? 'Saving…' : 'Save key'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={save.isPending}
              onClick={() => {
                setEditing(false);
                setKey('');
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}

      <details className="group mt-3 rounded-field border border-border/70 bg-muted/40">
        <summary className="flex cursor-pointer items-center gap-2 rounded-field px-3 py-2 text-xs font-bold tracking-wide text-muted-foreground select-none hover:text-foreground">
          <ChevronDown className="size-3.5 transition-transform group-open:rotate-180" aria-hidden />
          Documentation &amp; setup
        </summary>
        <div className="grid gap-3 border-t border-border/70 px-3 py-3 text-sm text-muted-foreground">
          <p>{integration.description}</p>
          <div>
            <p className="font-medium text-foreground">Get a key</p>
            <a
              className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
              href={integration.where_to_get}
              target="_blank"
              rel="noreferrer"
            >
              Create one in the {integration.label} console <ExternalLink className="size-3.5" aria-hidden />
            </a>
          </div>
          <div>
            <p className="font-medium text-foreground">How to enable</p>
            <ol className="list-decimal space-y-1 pl-5">
              {integration.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </div>
          <p className="text-xs">
            Used by
            {integration.used_by.map((endpoint) => (
              <code key={endpoint} className="mx-1 rounded bg-muted px-1 py-0.5 font-mono">
                {endpoint}
              </code>
            ))}
            · env fallback: <code className="rounded bg-muted px-1 py-0.5 font-mono">{integration.env_var}</code>
          </p>
          <p className="flex items-start gap-2 text-xs">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <span>{integration.security_note}</span>
          </p>
        </div>
      </details>

      <ConfirmDialog
        open={confirmingRemove}
        onOpenChange={setConfirmingRemove}
        title={`Remove ${integration.label} key?`}
        description={`The stored key is deleted and the app falls back to the ${integration.env_var} environment variable, if set. Nothing else is affected.`}
        confirmLabel="Remove key"
        destructive
        pending={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}

function StatusBadge({ integration }: { integration: Integration }) {
  if (integration.configured) {
    return (
      <Badge variant="success">
        <Check className="size-3" aria-hidden /> Configured
      </Badge>
    );
  }
  if (integration.stored_unreadable) {
    return (
      <Badge variant="destructive">
        <AlertTriangle className="size-3" aria-hidden /> Needs attention
      </Badge>
    );
  }
  return <Badge variant="secondary">Not set</Badge>;
}

function SourceLine({ integration }: { integration: Integration }) {
  const parts: string[] = [];
  if (integration.source === 'database') {
    parts.push(`saved in app${integration.key_hint ? ` · ends with ${integration.key_hint}` : ''}`);
    if (integration.updated_at) {
      parts.push(`updated ${formatWhen(integration.updated_at)}${integration.updated_by ? ` by ${integration.updated_by}` : ''}`);
    }
  } else if (integration.source === 'env') {
    parts.push(`from backend/.env (${integration.env_var})`);
  } else if (integration.stored_unreadable) {
    parts.push('a stored key exists but cannot be read');
  } else {
    parts.push('not configured — the related feature stays off until a key is set');
  }
  return <p className="mt-1 text-xs text-muted-foreground">{parts.join(' · ')}</p>;
}

function formatWhen(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}
