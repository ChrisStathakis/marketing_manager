import { Check, Copy, Link2, Palette, Store } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';
import { ApiKeysCard } from '@/components/ApiKeysCard';
import { PageHeader } from '@/components/PageHeader';
import { useAuthStore } from '@/lib/auth-store';
import { useTheme, type Theme } from '@/lib/theme';
import { cn } from '@/lib/utils';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { Field } from '@/ui/field';
import { Input } from '@/ui/input';

export default function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" description="Utilities and preferences." />
      <div className="space-y-4">
        <ApiKeysCard />
        <div className="grid gap-4 lg:grid-cols-2">
          <UtmBuilder />
          <div className="grid gap-4">
            <Appearance />
            <ShopIntegration />
            <Account />
          </div>
        </div>
      </div>
    </div>
  );
}

function UtmBuilder() {
  const [copied, setCopied] = useState(false);
  const [utm, setUtm] = useState({
    url: 'https://example-shop.com/product/basket',
    source: 'instagram',
    medium: 'social',
    campaign: 'fall-baskets',
    content: '',
  });
  const built =
    utm.url +
    `?utm_source=${encodeURIComponent(utm.source)}&utm_medium=${encodeURIComponent(utm.medium)}&utm_campaign=${encodeURIComponent(utm.campaign)}` +
    (utm.content ? `&utm_content=${encodeURIComponent(utm.content)}` : '');

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(built);
      setCopied(true);
      toast.success('UTM link copied');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Could not copy — select the text manually.');
    }
  };

  const field = (key: keyof typeof utm, label: string) => (
    <Field label={label} htmlFor={`utm-${key}`}>
      <Input
        id={`utm-${key}`}
        value={utm[key]}
        onChange={(e) => setUtm({ ...utm, [key]: e.target.value })}
      />
    </Field>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Link2 className="size-4 text-primary" /> UTM builder
        </CardTitle>
        <CardDescription>Tag links so orders and results can be attributed to campaigns.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {field('url', 'URL')}
        <div className="grid gap-3 sm:grid-cols-2">
          {field('source', 'Source')}
          {field('medium', 'Medium')}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {field('campaign', 'Campaign')}
          {field('content', 'Content (optional)')}
        </div>
        <div className="rounded-field border border-border bg-muted/50 p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Tagged link</p>
          <div className="flex items-start gap-2">
            <code className="min-w-0 flex-1 font-mono text-xs break-all">{built}</code>
            <Button variant="outline" size="sm" onClick={copy} className="shrink-0">
              {copied ? <Check /> : <Copy />} Copy
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

const THEMES: { value: Theme; label: string }[] = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'System' },
];

function Appearance() {
  const { theme, setTheme } = useTheme();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Palette className="size-4 text-primary" /> Appearance
        </CardTitle>
        <CardDescription>Theme preference is stored in this browser.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          {THEMES.map((t) => (
            <Button
              key={t.value}
              variant={theme === t.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => setTheme(t.value)}
              className={cn('flex-1')}
            >
              {t.label}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function ShopIntegration() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Store className="size-4 text-primary" /> Basket shop integration
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm text-muted-foreground">
        <p>
          v1 keeps the shop connection manual: create products and orders via{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">/api/products/</code> and{' '}
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">/api/orders/</code> (or the Django admin), and
          import daily results as CSV.
        </p>
        <p>
          Order rows carry <code className="font-mono text-xs">utm_*</code> values, so orders can be matched to the
          campaigns that drove them.
        </p>
      </CardContent>
    </Card>
  );
}

function Account() {
  const username = useAuthStore((s) => s.username) ?? 'user';
  const logout = useAuthStore((s) => s.logout);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
        <CardDescription>
          Signed in as <span className="font-medium text-foreground">{username}</span>
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button variant="outline" size="sm" onClick={logout}>
          Log out
        </Button>
      </CardContent>
    </Card>
  );
}
