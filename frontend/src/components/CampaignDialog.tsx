import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import type { Campaign } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/ui/dialog';
import { CampaignFormFields, campaignPayload, campaignToFormValues, useCampaignForm } from './CampaignForm';

interface CampaignDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Edit this campaign; leave unset to create a new one. */
  campaign?: Campaign | null;
  onSaved?: (campaign: Campaign) => void;
}

/** Create or edit a campaign with the shared validated form. */
export function CampaignDialog({ open, onOpenChange, campaign = null, onSaved }: CampaignDialogProps) {
  const qc = useQueryClient();
  const form = useCampaignForm(campaignToFormValues(campaign ?? undefined));

  useEffect(() => {
    if (open) form.reset(campaignToFormValues(campaign ?? undefined));
  }, [open, campaign, form]);

  const save = useMutation({
    mutationFn: async (values: Parameters<typeof campaignPayload>[0]) => {
      const payload = campaignPayload(values);
      return (
        campaign
          ? await api.patch<Campaign>(`/campaigns/${campaign.id}/`, payload)
          : await api.post<Campaign>('/campaigns/', payload)
      ).data;
    },
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: ['campaigns'] });
      qc.invalidateQueries({ queryKey: ['campaign', saved.id] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success(campaign ? 'Campaign updated' : `Campaign "${saved.name}" created`);
      onOpenChange(false);
      onSaved?.(saved);
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{campaign ? 'Edit campaign' : 'New campaign'}</DialogTitle>
          <DialogDescription>
            {campaign
              ? 'Update the plan — results, content and tasks stay linked.'
              : 'Only the name is required — you can fill in the rest now or later.'}
          </DialogDescription>
        </DialogHeader>
        {save.isError && (
          <Alert variant="destructive" className="mb-4">
            {getErrorMessage(save.error)}
          </Alert>
        )}
        <form id="campaign-form" noValidate onSubmit={form.handleSubmit((values) => save.mutate(values))}>
          <CampaignFormFields form={form} idPrefix={campaign ? 'edit-' : 'create-'} />
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>
            Cancel
          </Button>
          <Button type="submit" form="campaign-form" disabled={save.isPending}>
            {save.isPending ? 'Saving…' : campaign ? 'Save changes' : 'Create campaign'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
