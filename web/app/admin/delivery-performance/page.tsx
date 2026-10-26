'use client';

import {useEffect, useRef, useState} from 'react';
import {RefreshCw} from 'lucide-react';
import {api} from '@/lib/api';
import {Nav} from '@/components/Nav';

type Performance = {window_days: number; total_records: number; delivered: number; failed: number; active: number; median_assignment_to_pickup_seconds?: number | null; median_pickup_to_delivery_seconds?: number | null; basis: string};
const minutes = (seconds?: number | null) => seconds == null ? 'Not enough completed data' : `${Math.round(seconds / 60)} min median`;

export default function DeliveryPerformance() {
  const [data, setData] = useState<Performance | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latestRequest = useRef(0);

  async function load() {
    const request = ++latestRequest.current;
    setLoading(true);
    setError('');
    try {
      const nextData = await api<Performance>('/admin/delivery-performance');
      if (request !== latestRequest.current) return;
      setData(nextData);
    } catch (cause: unknown) {
      if (request !== latestRequest.current) return;
      setError(cause instanceof Error ? cause.message : 'Delivery performance is temporarily unavailable.');
    } finally {
      if (request === latestRequest.current) setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return <>
    <Nav/>
    <main className="container section adminOperations" aria-busy={loading}>
      <div className="sectionHead">
        <div>
          <span className="eyebrow">Recorded operations</span>
          <h2>Delivery performance</h2>
          <p className="muted">Factual 30-day timing from recorded delivery transitions. No predicted ETA or confidence score.</p>
        </div>
        <button type="button" className="btn secondary" onClick={load} disabled={loading} aria-label="Refresh delivery performance"><RefreshCw size={16}/>{loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>
      {loading && !data && <p className="muted" role="status">Loading delivery performance…</p>}
      {error && <div className="notice" role="alert">{data ? 'Unable to refresh delivery performance. Showing the last confirmed data. ' : 'Unable to load delivery performance. '}{error}<button type="button" className="btn secondary" onClick={load}>Retry delivery performance</button></div>}
      {data && <>
        <div className="statsGrid">
          <div className="card statCard"><span className="statValue">{data.delivered}</span><strong>Delivered</strong></div>
          <div className="card statCard"><span className="statValue">{data.failed}</span><strong>Failed</strong></div>
          <div className="card statCard"><span className="statValue">{data.active}</span><strong>Active</strong></div>
        </div>
        {data.total_records === 0
          ? <div className="panel muted">No delivery records are available for this window.</div>
          : <div className="panel"><div className="metricRow"><span>Assignment to pickup</span><strong>{minutes(data.median_assignment_to_pickup_seconds)}</strong></div><div className="metricRow"><span>Pickup to delivery</span><strong>{minutes(data.median_pickup_to_delivery_seconds)}</strong></div><p className="muted small">Basis: recorded timestamps from {data.total_records} delivery records in the last {data.window_days} days.</p></div>}
      </>}
    </main>
  </>;
}
