import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ExternalLink,
  KeyRound,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { fetchOne, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import type { Integration, IntegrationConfigField, IntegrationField, SyncResult } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Badge } from '@/ui/badge';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { Field } from '@/ui/field';
import { Input, Textarea } from '@/ui/input';
import { Skeleton } from '@/ui/skeleton';

/** Fallback spec for providers that only expose a single key. */
const DEFAULT_FIELDS: IntegrationField[] = [
  { name: 'key', label: 'API key', secret: true, min_length: 16, placeholder: 'Paste the key' },
];

const secretFields = (integration: Integration) =>
  integration.fields?.length ? integration.fields : DEFAULT_FIELDS;

const configFields = (integration: Integration) => integration.config_fields ?? [];

/** Status + in-app documentation for every third-party credential the backend uses. */
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
          <KeyRound className="size-4 text-primary" /> API keys &amp; integrations
        </CardTitle>
        <CardDescription>
          Credentials for services the backend calls. They live server-side only — encrypted at rest, never part of the
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
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [secrets, setSecrets] = useState<Record<string, string>>({});
  const [config, setConfig] = useState<Record<string, string>>({});
  const [confirmingRemove, setConfirmingRemove] = useState(false);

  const fields = secretFields(integration);
  const settings = configFields(integration);

  const secretValue = (name: string) => secrets[name] ?? '';
  const configValue = (name: string) => config[name] ?? integration.config[name] ?? '';

  const reset = () => {
    setSecrets({});
    setConfig({});
  };

  const save = useMutation({
    mutationFn: async () => {
      const payload = {
        fields: Object.fromEntries(
          fields
            .map((field) => [field.name, secretValue(field.name).trim()] as const)
            .filter(([, value]) => value !== ''),
        ),
        config: Object.fromEntries(settings.map((field) => [field.name, configValue(field.name).trim()] as const)),
      };
      const { data } = await api.put<Integration>(`/integrations/${integration.id}/`, payload);
      return data;
    },
    onSuccess: () => {
      onChanged();
      setEditing(false);
      reset();
      toast.success(`${integration.label} settings saved`);
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

  const sync = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<SyncResult>(integration.sync_endpoint as string, {});
      return data;
    },
    onSuccess: (result) => {
      onChanged();
      qc.invalidateQueries({ queryKey: qk.metricsRoot });
      qc.invalidateQueries({ queryKey: qk.dashboardRoot });
      const summary = `${result.created} created · ${result.updated} updated · ${result.skipped} skipped`;
      if (result.unmatched.length > 0) {
        toast.warning(`Synced ${result.start} → ${result.end}`, {
          description: `${summary}. No campaign matches: ${result.unmatched.join(', ')}`,
        });
      } else {
        toast.success(`Synced ${result.start} → ${result.end}`, { description: summary });
      }
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const tooShort = fields.some((field) => {
    const value = secretValue(field.name).trim();
    return value !== '' && value.length < (field.min_length ?? 0);
  });
  const hasSecret = fields.some((field) => secretValue(field.name).trim() !== '');
  const configChanged = settings.some(
    (field) => configValue(field.name).trim() !== (integration.config[field.name] ?? '').trim(),
  );
  const canSave = (hasSecret || configChanged) && !tooShort;

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
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button size="sm" variant={integration.configured ? 'outline' : 'default'} onClick={() => setEditing(true)}>
              {integration.stored ? 'Settings' : 'Set up'}
            </Button>
            {integration.sync_endpoint && integration.configured && (
              <Button size="sm" variant="outline" onClick={() => sync.mutate()} disabled={sync.isPending}>
                <RefreshCw className={sync.isPending ? 'animate-spin' : undefined} />
                {sync.isPending ? 'Syncing…' : 'Sync now'}
              </Button>
            )}
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

      {integration.last_sync_error !== '' && (
        <Alert variant="destructive" className="mt-3" title="Last sync failed">
          {integration.last_sync_error}
        </Alert>
      )}

      {editing && (
        <div className="mt-3 grid gap-3 rounded-field border border-border/70 bg-muted/30 p-3">
          {fields.map((field) => (
            <SecretField
              key={field.name}
              id={`integration-${integration.id}-${field.name}`}
              field={field}
              value={secretValue(field.name)}
              stored={integration.stored}
              onChange={(value) => setSecrets((prev) => ({ ...prev, [field.name]: value }))}
            />
          ))}

          {settings.map((field) => (
            <ConfigField
              key={field.name}
              id={`integration-${integration.id}-${field.name}`}
              field={field}
              value={configValue(field.name)}
              onChange={(value) => setConfig((prev) => ({ ...prev, [field.name]: value }))}
            />
          ))}

          <div className="flex gap-2">
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending || !canSave}>
              {save.isPending ? 'Saving…' : 'Save'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={save.isPending}
              onClick={() => {
                setEditing(false);
                reset();
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
            <p className="font-medium text-foreground">Where to get it</p>
            <a
              className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
              href={integration.where_to_get}
              target="_blank"
              rel="noreferrer"
            >
              Open the {integration.label} console <ExternalLink className="size-3.5" aria-hidden />
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

function SecretField({
  id,
  field,
  value,
  stored,
  onChange,
}: {
  id: string;
  field: IntegrationField;
  value: string;
  stored: boolean;
  onChange: (value: string) => void;
}) {
  const trimmed = value.trim();
  const wrongPrefix = Boolean(field.prefix) && trimmed !== '' && !trimmed.startsWith(field.prefix as string);
  const tooShort = trimmed !== '' && trimmed.length < (field.min_length ?? 0);

  let hint = field.hint ?? '';
  if (stored) {
    hint = `${hint} Leave blank to keep the current key.`.trim();
  }
  if (wrongPrefix) {
    hint = `Expected a value starting with "${field.prefix}" — double-check it.`;
  }
  if (tooShort) {
    hint = `Minimum ${field.min_length} characters.`;
  }

  const shared = {
    id,
    autoComplete: 'off' as const,
    spellCheck: false,
    placeholder: field.placeholder ?? (stored ? 'New value (leave blank to keep)' : 'Paste the value'),
    value,
    onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.target.value),
  };

  return (
    <Field label={field.label} htmlFor={id} hint={hint}>
      {field.multiline ? (
        <Textarea {...shared} rows={6} className="font-mono text-xs" />
      ) : (
        <Input {...shared} type="password" />
      )}
    </Field>
  );
}

function ConfigField({
  id,
  field,
  value,
  onChange,
}: {
  id: string;
  field: IntegrationConfigField;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field
      label={field.label}
      htmlFor={id}
      hint={field.required ? field.hint : field.hint ? `${field.hint} Optional.` : 'Optional.'}
    >
      <Input
        id={id}
        autoComplete="off"
        spellCheck={false}
        placeholder={field.placeholder}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
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
    parts.push(`saved in app${integration.key_hint ? ` · ${integration.key_hint}` : ''}`);
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
  if (integration.last_synced_at) {
    parts.push(`last synced ${formatWhen(integration.last_synced_at)}`);
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
