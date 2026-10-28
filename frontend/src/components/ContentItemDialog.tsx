import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link2 } from 'lucide-react';
import { useEffect } from 'react';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';
import api from '@/lib/api';
import { fetchList, qk } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import { dateTimeLocalToISO, toDateTimeLocalValue } from '@/lib/format';
import type { Campaign, Channel, ContentItem } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { Field } from '@/ui/field';
import { Input, Textarea } from '@/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';

const schema = z.object({
  campaign: z.string().min(1, 'Choose a campaign.'),
  channel: z.string(),
  title: z.string().trim().min(1, 'Title is required.').max(255, 'Keep it under 255 characters.'),
  copy: z.string(),
  asset_url: z.string().trim().url('Enter a valid URL (https://…).').or(z.literal('')),
  link: z.string().trim().url('Enter a valid URL (https://…).').or(z.literal('')),
  utm_source: z.string().trim().max(255),
  utm_medium: z.string().trim().max(255),
  utm_campaign: z.string().trim().max(255),
  utm_content: z.string().trim().max(255),
  locale: z.string(),
  format: z.string(),
  content_kind: z.string(),
  thread: z.string(),
  notes: z.string(),
  status: z.enum(['draft', 'scheduled', 'published']),
  publish_at: z.string(),
});

type Values = z.infer<typeof schema>;

interface ContentItemDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When set, the dialog edits this item; otherwise it creates a new one. */
  item?: ContentItem | null;
  defaultCampaignId?: number;
  /** yyyy-mm-dd preset for publish_at when creating from the calendar. */
  defaultDate?: string;
}

function defaults(item: ContentItem | null | undefined, defaultCampaignId?: number, defaultDate?: string): Values {
  return {
    campaign: item ? String(item.campaign) : defaultCampaignId ? String(defaultCampaignId) : '',
    channel: item?.channel ? String(item.channel) : '',
    title: item?.title ?? '',
    copy: item?.copy ?? '',
    asset_url: item?.asset_url ?? '',
    link: item?.link ?? '',
    utm_source: item?.utm_source ?? '',
    utm_medium: item?.utm_medium ?? '',
    utm_campaign: item?.utm_campaign ?? '',
    utm_content: item?.utm_content ?? '',
    locale: item?.locale ?? '',
    format: item?.format ?? '',
    content_kind: item?.content_kind ?? '',
    thread: item?.thread?.join('\n\n') ?? '',
    notes: item?.notes ?? '',
    status: item?.status ?? 'draft',
    publish_at: item ? toDateTimeLocalValue(item.publish_at) : defaultDate ? `${defaultDate}T12:00` : '',
  };
}

export function ContentItemDialog({ open, onOpenChange, item, defaultCampaignId, defaultDate }: ContentItemDialogProps) {
  const qc = useQueryClient();
  const campaigns = useQuery({
    queryKey: qk.campaigns({ page_size: 200 }),
    queryFn: () => fetchList<Campaign>('/campaigns/', { page_size: 200, ordering: 'name' }),
    enabled: open,
  });
  const channels = useQuery({
    queryKey: qk.channels({ page_size: 200 }),
    queryFn: () => fetchList<Channel>('/channels/', { page_size: 200, ordering: 'name' }),
    enabled: open,
  });

  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: defaults(item, defaultCampaignId, defaultDate) });
  const { control, register, handleSubmit, reset, setValue, getValues, formState: { errors } } = form;

  useEffect(() => {
    if (open) reset(defaults(item, defaultCampaignId, defaultDate));
  }, [open, item, defaultCampaignId, defaultDate, reset]);

  const save = useMutation({
    mutationFn: async (values: Values) => {
      const payload = {
        campaign: Number(values.campaign),
        channel: values.channel ? Number(values.channel) : null,
        title: values.title,
        copy: values.copy,
        asset_url: values.asset_url,
        link: values.link,
        utm_source: values.utm_source,
        utm_medium: values.utm_medium,
        utm_campaign: values.utm_campaign,
        utm_content: values.utm_content,
        locale: values.locale,
        format: values.format,
        content_kind: values.content_kind,
        thread: values.thread
          .split(/\n\s*\n/)
          .map((tweet) => tweet.trim())
          .filter(Boolean),
        notes: values.notes,
        status: values.status,
        publish_at: dateTimeLocalToISO(values.publish_at),
      };
      return item ? (await api.patch(`/content/${item.id}/`, payload)).data : (await api.post('/content/', payload)).data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['content'] });
      qc.invalidateQueries({ queryKey: ['campaign'] });
      toast.success(item ? 'Content item updated' : 'Content item created');
      onOpenChange(false);
    },
  });

  const link = useWatch({ control, name: 'link' });
  const utmSource = useWatch({ control, name: 'utm_source' });
  const utmMedium = useWatch({ control, name: 'utm_medium' });
  const utmCampaign = useWatch({ control, name: 'utm_campaign' });
  const utmContent = useWatch({ control, name: 'utm_content' });
  const preview =
    link && (utmSource || utmMedium || utmCampaign || utmContent)
      ? `${link}?utm_source=${encodeURIComponent(utmSource)}&utm_medium=${encodeURIComponent(utmMedium)}&utm_campaign=${encodeURIComponent(utmCampaign)}${utmContent ? `&utm_content=${encodeURIComponent(utmContent)}` : ''}`
      : null;

  const onCampaignChange = (value: string) => {
    setValue('campaign', value, { shouldValidate: true });
    const campaign = campaigns.data?.results.find((c) => String(c.id) === value);
    if (campaign && !getValues('utm_campaign')) setValue('utm_campaign', campaign.utm_campaign);
  };
  const onChannelChange = (value: string) => {
    setValue('channel', value === 'none' ? '' : value);
    const channel = channels.data?.results.find((c) => String(c.id) === value);
    if (channel && !getValues('utm_source')) setValue('utm_source', channel.channel_type);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{item ? 'Edit content item' : 'New content item'}</DialogTitle>
          <DialogDescription>
            Plan a post, story or ad. Fill in the UTM fields to keep attribution consistent.
          </DialogDescription>
        </DialogHeader>
        {save.isError && (
          <Alert variant="destructive" className="mb-4">
            {getErrorMessage(save.error)}
          </Alert>
        )}
        <form
          id="content-form"
          noValidate
          onSubmit={handleSubmit((values) => save.mutate(values))}
          className="grid gap-4"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Campaign" error={errors.campaign?.message}>
              <Controller
                control={control}
                name="campaign"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={onCampaignChange}>
                    <SelectTrigger aria-label="Campaign">
                      <SelectValue placeholder="Choose a campaign…" />
                    </SelectTrigger>
                    <SelectContent>
                      {(campaigns.data?.results ?? []).map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Channel" error={errors.channel?.message} hint="Where it will be published.">
              <Controller
                control={control}
                name="channel"
                render={({ field }) => (
                  <Select value={field.value || 'none'} onValueChange={onChannelChange}>
                    <SelectTrigger aria-label="Channel">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No specific channel</SelectItem>
                      {(channels.data?.results ?? []).map((c) => (
                        <SelectItem key={c.id} value={String(c.id)}>
                          {c.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
          </div>
          <Field label="Title" htmlFor="content-title" error={errors.title?.message}>
            <Input id="content-title" placeholder="e.g. TikTok hook video #2" {...register('title')} />
          </Field>
          <Field label="Copy / caption" htmlFor="content-copy" error={errors.copy?.message}>
            <Textarea id="content-copy" rows={3} placeholder="Caption text, hashtags, CTA…" {...register('copy')} />
          </Field>
          <Field
            label="X / thread"
            htmlFor="content-thread"
            hint="One tweet per blank line. Copied straight into the post when it is time."
          >
            <Textarea
              id="content-thread"
              rows={4}
              placeholder={'1/ The number first…\n\n2/ The context…\n\n3/ Full table →'}
              {...register('thread')}
            />
          </Field>
          <Field label="Internal notes" htmlFor="content-notes">
            <Textarea id="content-notes" rows={2} placeholder="Asset owner, approval, source…" {...register('notes')} />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Status" error={errors.status?.message}>
              <Controller
                control={control}
                name="status"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger aria-label="Status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft</SelectItem>
                      <SelectItem value="scheduled">Scheduled</SelectItem>
                      <SelectItem value="published">Published</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Publish at" htmlFor="content-publish" error={errors.publish_at?.message}>
              <Input id="content-publish" type="datetime-local" {...register('publish_at')} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Link" htmlFor="content-link" error={errors.link?.message} hint="Where the post points (shop page, landing…).">
              <Input id="content-link" placeholder="https://…" {...register('link')} />
            </Field>
            <Field label="Asset URL" htmlFor="content-asset" error={errors.asset_url?.message} hint="Image/video file link (optional).">
              <Input id="content-asset" placeholder="https://…" {...register('asset_url')} />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Language">
              <Controller
                control={control}
                name="locale"
                render={({ field }) => (
                  <Select value={field.value || 'none'} onValueChange={(value) => field.onChange(value === 'none' ? '' : value)}>
                    <SelectTrigger aria-label="Language">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Not set</SelectItem>
                      <SelectItem value="el">Ελληνικά</SelectItem>
                      <SelectItem value="en">English</SelectItem>
                      <SelectItem value="tr">Türkçe</SelectItem>
                      <SelectItem value="sr">Srpski</SelectItem>
                      <SelectItem value="lt">Lietuvių</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Format">
              <Controller
                control={control}
                name="format"
                render={({ field }) => (
                  <Select value={field.value || 'none'} onValueChange={(value) => field.onChange(value === 'none' ? '' : value)}>
                    <SelectTrigger aria-label="Format">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Not set</SelectItem>
                      <SelectItem value="post">Feed post</SelectItem>
                      <SelectItem value="carousel">Carousel</SelectItem>
                      <SelectItem value="reel">Reel / short video</SelectItem>
                      <SelectItem value="story">Story</SelectItem>
                      <SelectItem value="thread">Thread</SelectItem>
                      <SelectItem value="photo_carousel">Photo carousel</SelectItem>
                      <SelectItem value="short">Short video</SelectItem>
                      <SelectItem value="text_post">Text post</SelectItem>
                      <SelectItem value="video">Video</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
            <Field label="Card type" hint="Optional — links to the growth card.">
              <Controller
                control={control}
                name="content_kind"
                render={({ field }) => (
                  <Select value={field.value || 'none'} onValueChange={(value) => field.onChange(value === 'none' ? '' : value)}>
                    <SelectTrigger aria-label="Card type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Not set</SelectItem>
                      <SelectItem value="top8">Top 8</SelectItem>
                      <SelectItem value="team">Team card</SelectItem>
                      <SelectItem value="team_delta">Team season delta</SelectItem>
                      <SelectItem value="round_recap">Round recap</SelectItem>
                      <SelectItem value="player">Player card</SelectItem>
                      <SelectItem value="metric">Metric</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-4">
            <Field label="UTM source" htmlFor="content-utm-source" error={errors.utm_source?.message}>
              <Input id="content-utm-source" placeholder="instagram" {...register('utm_source')} />
            </Field>
            <Field label="UTM medium" htmlFor="content-utm-medium" error={errors.utm_medium?.message}>
              <Input id="content-utm-medium" placeholder="social" {...register('utm_medium')} />
            </Field>
            <Field label="UTM campaign" htmlFor="content-utm-campaign" error={errors.utm_campaign?.message}>
              <Input id="content-utm-campaign" placeholder="top8-r7" {...register('utm_campaign')} />
            </Field>
            <Field label="UTM content" htmlFor="content-utm-content" error={errors.utm_content?.message}>
              <Input id="content-utm-content" placeholder="carousel_el" {...register('utm_content')} />
            </Field>
          </div>
          {preview && (
            <div className="rounded-field border border-border bg-muted/50 p-3">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Link2 className="size-3.5" /> Tagged link preview
              </p>
              <code className="font-mono text-xs break-all">{preview}</code>
            </div>
          )}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="content-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : item ? 'Save changes' : 'Create item'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
