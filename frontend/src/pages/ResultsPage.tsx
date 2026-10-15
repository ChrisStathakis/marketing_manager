import { useState } from 'react';
import api from '../lib/api';

export default function ResultsPage() {
  const [msg, setMsg] = useState('');
  const upload = async (url: string, file: File | undefined) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const { data } = await api.post(url, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMsg(`OK: created ${data.created}, updated ${data.updated}`);
    } catch {
      setMsg('Upload failed. Expected columns e.g. campaign,date,revenue,orders,spend.');
    }
  };
  return (
    <div>
      <h1>Record results</h1>
      <p>CSV columns (metrics): <code>campaign,date,revenue,orders,spend,ctr,roas</code></p>
      <p>CSV columns (spend): <code>campaign,channel,date,spend,impressions,clicks,conversions</code></p>
      <label>Metrics CSV <input type="file" accept=".csv" onChange={(e) => upload('/metrics/import-csv/', e.target.files?.[0])} /></label>
      <label>Spend CSV <input type="file" accept=".csv" onChange={(e) => upload('/spend/import-csv/', e.target.files?.[0])} /></label>
      {msg && <p role="status">{msg}</p>}
    </div>
  );
}
