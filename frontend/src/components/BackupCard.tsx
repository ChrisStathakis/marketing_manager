import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Database, Download, Upload } from 'lucide-react';
import { useRef, useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { downloadFile } from '@/lib/data';
import { getErrorMessage } from '@/lib/errors';
import type { RestoreResult } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Button } from '@/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { ConfirmDialog } from '@/ui/confirm-dialog';
import { Input } from '@/ui/input';

const INCLUDED = 'campaigns, channels, content, results, ad spend, tasks, suggestions, products and orders';

const stamp = () => new Date().toISOString().slice(0, 10);

/** Export the whole dataset, or replace it from a previous backup file. */
export function BackupCard() {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [confirming, setConfirming] = useState(false);

  const fileName = file?.name.toLowerCase() ?? '';
  const isDatabaseFile = fileName.endsWith('.sqlite3') || fileName.endsWith('.sqlite');

  const exportJson = useMutation({
    mutationFn: () => downloadFile('/backup/export/', undefined, `marketing-backup-${stamp()}.json`),
    onSuccess: () => toast.success('Backup downloaded'),
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const exportDatabase = useMutation({
    mutationFn: () => downloadFile('/backup/database/', undefined, `marketing-db-${stamp()}.sqlite3`),
    onSuccess: () => toast.success('Database downloaded'),
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  const restore = useMutation({
    mutationFn: async (chosen: File) => {
      const body = new FormData();
      body.append('file', chosen);
      body.append('confirm', 'replace');
      const { data } = await api.post<RestoreResult>('/backup/restore/', body);
      return data;
    },
    onSuccess: (result) => {
      qc.invalidateQueries();
      setConfirming(false);
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
      const total = result.restored ? Object.values(result.restored).reduce((sum, n) => sum + n, 0) : undefined;
      toast.success(result.detail, { description: total !== undefined ? `${total} rows restored` : undefined });
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="size-4 text-primary" /> Backup &amp; restore
        </CardTitle>
        <CardDescription>Download a copy of your data, or replace everything from a previous backup.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-sm font-medium text-foreground">Export</p>
          <p className="mt-1 text-sm text-muted-foreground">
            The JSON backup contains your {INCLUDED}. Accounts, passwords and saved API keys are never included. The
            database download is a full SQLite copy and does include accounts.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => exportJson.mutate()} disabled={exportJson.isPending}>
              <Download /> {exportJson.isPending ? 'Preparing…' : 'Download data (JSON)'}
            </Button>
            <Button size="sm" variant="outline" onClick={() => exportDatabase.mutate()} disabled={exportDatabase.isPending}>
              <Download /> {exportDatabase.isPending ? 'Preparing…' : 'Download database (SQLite)'}
            </Button>
          </div>
        </div>

        <div className="border-t border-border pt-4">
          <p className="text-sm font-medium text-foreground">Restore</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload a JSON backup to replace all data, or a{' '}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">.sqlite3</code> file to swap the whole
            database (that one needs a server restart).
          </p>
          <Input
            ref={fileRef}
            type="file"
            accept=".json,.sqlite3,.sqlite,application/json"
            className="mt-3"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          {file && (
            <Alert variant="destructive" className="mt-3" title="This replaces your current data">
              Restoring <span className="font-medium text-foreground">{file.name}</span> deletes the existing{' '}
              {isDatabaseFile ? 'database (a .bak copy is kept)' : 'business data'} and loads the file instead. This
              cannot be undone.
            </Alert>
          )}
          <Button
            size="sm"
            variant="destructive"
            className="mt-3"
            disabled={!file || restore.isPending}
            onClick={() => setConfirming(true)}
          >
            <Upload /> Restore from file
          </Button>
        </div>
      </CardContent>

      <ConfirmDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Replace all data?"
        description={
          isDatabaseFile
            ? 'The server database file is overwritten with the uploaded one (a .bak copy of the current file is kept). Restart the server afterwards.'
            : 'Every campaign, channel, content item, result, task, suggestion, product and order is deleted and replaced with the backup. Accounts and API keys are kept.'
        }
        confirmLabel="Replace everything"
        destructive
        pending={restore.isPending}
        onConfirm={() => file && restore.mutate(file)}
      />
    </Card>
  );
}
