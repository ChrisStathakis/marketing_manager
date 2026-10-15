import { useState } from 'react';

export default function SettingsPage() {
  const [base, setBase] = useState('');
  const [utm, setUtm] = useState({ source: 'instagram', medium: 'social', campaign: 'fall-baskets', url: 'https://example-shop.com/product/basket' });
  const built = `${utm.url}?utm_source=${encodeURIComponent(utm.source)}&utm_medium=${encodeURIComponent(utm.medium)}&utm_campaign=${encodeURIComponent(utm.campaign)}`;
  return (
    <div>
      <h1>Settings & shop link</h1>
      <section className="card">
        <h2>Basket website API (optional)</h2>
        <p>Point the backend shop sync at your store (Woo/Shopify/custom). v1 supports manual product/order entry via <code>/api/products/</code> and <code>/api/orders/</code> plus CSV results.</p>
        <label>Shop API base<input value={base} onChange={(e) => setBase(e.target.value)} placeholder="https://shop.example.com/wp-json/wc/v3" /></label>
      </section>
      <section className="card">
        <h2>UTM builder</h2>
        <div className="grid2">
          <label>URL<input value={utm.url} onChange={(e) => setUtm({ ...utm, url: e.target.value })} /></label>
          <label>Source<input value={utm.source} onChange={(e) => setUtm({ ...utm, source: e.target.value })} /></label>
          <label>Medium<input value={utm.medium} onChange={(e) => setUtm({ ...utm, medium: e.target.value })} /></label>
          <label>Campaign<input value={utm.campaign} onChange={(e) => setUtm({ ...utm, campaign: e.target.value })} /></label>
        </div>
        <p><code>{built}</code></p>
      </section>
    </div>
  );
}
