import { UploadCloud } from 'lucide-react';
import { useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import api from '@/lib/api';
import { getErrorMessage } from '@/lib/errors';
import type { ImportResult } from '@/lib/types';
import { Alert } from '@/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/ui/table';

export default function ResultsPage() {
  return (
    <div>
      <PageHeader
        title="Record results"
        description="Import daily metrics and ad spend from CSV. Invalid rows are skipped and reported with their line number."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <ImportCard
          title="Metrics CSV"
          description="Daily revenue, orders, spend and CTR per campaign."
          columns={['campaign', 'date', 'revenue', 'orders', 'spend', 'ctr', 'roas (optional)']}
          sample={'campaign,date,revenue,orders,spend,ctr\n1,2026-10-01,120.00,4,40.00,0.4'}
          endpoint="/metrics/import-csv/"
        />
        <ImportCard
          title="Spend CSV"
          description="Ad spend and delivery stats per campaign and channel."
          columns={['campaign', 'channel (optional)', 'date', 'spend', 'impressions', 'clicks', 'conversions']}
          sample={'campaign,channel,date,spend,impressions,clicks,conversions\n1,1,2026-10-01,30.00,1000,50,5'}
          endpoint="/spend/import-csv/"
        />
      </div>
    </div>
  );
}

function ImportCard({
  title,
  description,
  columns,
  sample,
  endpoint,
}: {
  title: string;
  description: string;
  columns: string[];
  sample: string;
  endpoint: string;
}) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    setError(null);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const { data } = await api.post<ImportResult>(endpoint, fd);
      setResult(data);
    } catch (ex) {
      setError(getErrorMessage(ex, 'Upload failed.'));
    } finally {
      setBusy(false);
    }
  };

  const downloadSample = () => {
    const blob = new Blob([sample + '\n'], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${endpoint.includes('spend') ? 'spend' : 'metrics'}-template.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Columns: <code className="rounded bg-muted px-1 py-0.5 font-mono">{columns.join(', ')}</code>{' '}
          <button onClick={downloadSample} className="font-medium text-primary hover:underline">
            Download template
          </button>
        </p>
        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            void upload(e.dataTransfer.files?.[0]);
          }}
          className={
            'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors ' +
            (dragOver ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 hover:bg-muted/50')
          }
        >
          <UploadCloud className="size-6 text-muted-foreground" aria-hidden />
          <span className="text-sm font-medium">{busy ? 'Importing…' : 'Drop a CSV here or click to choose'}</span>
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            disabled={busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              void upload(file);
            }}
          />
        </label>
        {error && <Alert variant="destructive">{error}</Alert>}
        {result && (
          <Alert variant={result.error_count > 0 ? 'info' : 'success'}>
            <p>
              Imported: <strong>{result.created}</strong> new, <strong>{result.updated}</strong> updated.
              {result.error_count > 0 && (
                <>
                  {' '}
                  <strong>{result.error_count}</strong> row(s) skipped.
                </>
              )}
            </p>
          </Alert>
        )}
        {result && result.errors.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-20">Line</TableHead>
                <TableHead>Problem</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {result.errors.map((e, i) => (
                <TableRow key={`${e.row}-${i}`}>
                  <TableCell className="tabular-nums">{e.row}</TableCell>
                  <TableCell className="text-destructive">{e.error}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
