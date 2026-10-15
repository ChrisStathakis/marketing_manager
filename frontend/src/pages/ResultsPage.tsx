import { useState } from 'react';
import api from '../lib/api';

interface ImportResult {
  created: number;
  updated: number;
  error_count?: number;
  errors?: { row: number; error: string }[];
}

export default function ResultsPage() {
  const [msg, setMsg] = useState('');
  const [errors, setErrors] = useState<{ row: number; error: string }[]>([]);
  const [busy, setBusy] = useState(false);

  const upload = async (url: string, file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setMsg('');
    setErrors([]);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const { data } = await api.post<ImportResult>(url, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMsg(`Imported: ${data.created} new, ${data.updated} updated.`);
      setErrors(data.errors ?? []);
    } catch (ex) {
      const detail =
        (ex as { response?: { data?: { detail?: string } } }).response?.data?.detail ??
        'Upload failed. Expected columns e.g. campaign,date,revenue,orders,spend.';
      setMsg(detail);
    } finally {
      setBusy(false);
    }
  };

  const onPick = (url: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-uploading the same file
    void upload(url, file);
  };

  return (
    <div>
      <h1>Record results</h1>
      <p>CSV columns (metrics): <code>campaign,date,revenue,orders,spend,ctr,roas</code> — roas is derived from revenue/spend when omitted.</p>
      <p>CSV columns (spend): <code>campaign,channel,date,spend,impressions,clicks,conversions</code></p>
      <label>Metrics CSV <input type="file" accept=".csv" disabled={busy} onChange={onPick('/metrics/import-csv/')} /></label>
      <label>Spend CSV <input type="file" accept=".csv" disabled={busy} onChange={onPick('/spend/import-csv/')} /></label>
      {busy && <p role="status">Importing…</p>}
      {msg && <p role="status">{msg}</p>}
      {errors.length > 0 && (
        <div role="alert" className="card">
          <strong>{errors.length} row(s) skipped:</strong>
          <ul>
            {errors.map((e) => (
              <li key={`${e.row}-${e.error}`}>Line {e.row}: {e.error}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
