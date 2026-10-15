import { zodResolver } from '@hookform/resolvers/zod';
import { Controller, useForm, type UseFormReturn } from 'react-hook-form';
import { z } from 'zod';
import { Field } from '@/ui/field';
import { Input, Textarea } from '@/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/ui/select';
import type { Campaign } from '@/lib/types';

export const CAMPAIGN_STATUSES = ['draft', 'planned', 'active', 'paused', 'completed'] as const;

export const campaignSchema = z
  .object({
    name: z.string().trim().min(1, 'Name is required.').max(255, 'Keep it under 255 characters.'),
    objective: z.string().trim().max(2000, 'Keep it under 2000 characters.'),
    budget: z.string().trim().regex(/^\d+(\.\d{1,2})?$/, 'Enter an amount like 500 or 500.00.'),
    status: z.enum(CAMPAIGN_STATUSES),
    start_date: z.string(),
    end_date: z.string(),
    utm_campaign: z.string().trim().max(255, 'Keep it under 255 characters.'),
  })
  .superRefine((values, ctx) => {
    if (values.start_date && values.end_date && values.end_date < values.start_date) {
      ctx.addIssue({
        code: 'custom',
        path: ['end_date'],
        message: 'End date must be on or after the start date.',
      });
    }
  });

export type CampaignFormValues = z.infer<typeof campaignSchema>;

export function campaignToFormValues(campaign?: Campaign): CampaignFormValues {
  return {
    name: campaign?.name ?? '',
    objective: campaign?.objective ?? '',
    budget: campaign?.budget ?? '0',
    status: campaign?.status ?? 'draft',
    start_date: campaign?.start_date ?? '',
    end_date: campaign?.end_date ?? '',
    utm_campaign: campaign?.utm_campaign ?? '',
  };
}

export function useCampaignForm(defaults?: CampaignFormValues) {
  return useForm<CampaignFormValues>({
    resolver: zodResolver(campaignSchema),
    defaultValues: defaults ?? campaignToFormValues(),
  });
}

/** Form values -> API payload (empty optional strings become null/''). */
export function campaignPayload(values: CampaignFormValues) {
  return {
    ...values,
    budget: values.budget || '0',
    start_date: values.start_date || null,
    end_date: values.end_date || null,
  };
}

export function CampaignFormFields({ form, idPrefix = '' }: { form: UseFormReturn<CampaignFormValues>; idPrefix?: string }) {
  const {
    register,
    control,
    formState: { errors },
  } = form;
  const id = (name: string) => `${idPrefix}${name}`;
  return (
    <div className="grid gap-4">
      <Field label="Name" htmlFor={id('name')} error={errors.name?.message}>
        <Input id={id('name')} autoFocus {...register('name')} />
      </Field>
      <Field label="Objective" htmlFor={id('objective')} error={errors.objective?.message} hint="What does this campaign need to achieve?">
        <Textarea id={id('objective')} rows={2} {...register('objective')} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Budget (€)" htmlFor={id('budget')} error={errors.budget?.message}>
          <Input id={id('budget')} inputMode="decimal" {...register('budget')} />
        </Field>
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
                  {CAMPAIGN_STATUSES.map((s) => (
                    <SelectItem key={s} value={s} className="capitalize">
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Start date" htmlFor={id('start_date')} error={errors.start_date?.message}>
          <Input id={id('start_date')} type="date" {...register('start_date')} />
        </Field>
        <Field label="End date" htmlFor={id('end_date')} error={errors.end_date?.message}>
          <Input id={id('end_date')} type="date" {...register('end_date')} />
        </Field>
      </div>
      <Field
        label="UTM campaign"
        htmlFor={id('utm_campaign')}
        error={errors.utm_campaign?.message}
        hint="Used to attribute orders and results (utm_campaign value)."
      >
        <Input id={id('utm_campaign')} placeholder="fall-baskets" {...register('utm_campaign')} />
      </Field>
    </div>
  );
}
