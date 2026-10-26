'use client';

import {useEffect, useRef, useState} from 'react';
import {AlertTriangle, RefreshCw, RotateCcw, Truck} from 'lucide-react';
import {gaonApi, Order, Delivery, AdminOverview} from '@/lib/api';
import {Nav} from '@/components/Nav';

const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());

export default function AdminOperations() {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latestRequest = useRef(0);

  async function load() {
    const request = ++latestRequest.current;
    setLoading(true);
    setError('');
    try {
      const [nextOrders, nextDeliveries, nextOverview] = await Promise.all([
        gaonApi.merchantOrders(),
        gaonApi.myDeliveries(),
        gaonApi.adminOverview(),
      ]);
      if (request !== latestRequest.current) return;
      setOrders(nextOrders);
      setDeliveries(nextDeliveries);
      setOverview(nextOverview);
      setHasLoaded(true);
    } catch (cause: unknown) {
      if (request !== latestRequest.current) return;
      setError(cause instanceof Error ? cause.message : 'Operations data is temporarily unavailable.');
    } finally {
      if (request === latestRequest.current) setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const exceptions = deliveries.filter(delivery => delivery.status === 'failed');
  const refunds = orders.filter(order => order.payment_status === 'refunded');
  const unassigned = deliveries.filter(delivery => delivery.status === 'unassigned');

  return <>
    <Nav/>
    <main className="container section adminOperations" aria-busy={loading}>
      <div className="sectionHead">
        <div>
          <span className="eyebrow">Admin control room</span>
          <h2>Operations &amp; exceptions</h2>
          <p className="muted">Read backend-owned order, delivery, exception and refund state in one place.</p>
        </div>
        <button type="button" className="btn secondary" onClick={load} disabled={loading} aria-label="Refresh operations"><RefreshCw size={16}/>{loading ? 'Refreshing…' : 'Refresh'}</button>
      </div>
      {loading && !hasLoaded && <p className="muted" role="status">Loading operations…</p>}
      {error && <div className="notice" role="alert">{hasLoaded ? 'Unable to refresh operations. Showing the last confirmed data. ' : 'Unable to load operations. '}{error}<button type="button" className="btn secondary" onClick={load}>Retry operations</button></div>}
      {hasLoaded && <>
        <div className="statsGrid">
          <div className="card statCard"><Truck/><span className="statValue">{overview?.operations.ready_unassigned_deliveries ?? unassigned.length}</span><strong>Ready / unassigned</strong></div>
          <div className="card statCard"><AlertTriangle/><span className="statValue">{exceptions.length}</span><strong>Delivery exceptions</strong></div>
          <div className="card statCard"><RotateCcw/><span className="statValue">{refunds.length}</span><strong>Refunded orders</strong></div>
        </div>
        <section className="section">
          <h2 className="subhead">Delivery exceptions</h2>
          <div className="stack">
            {exceptions.map(delivery => <div className="panel" key={delivery.id}><div className="row space"><strong>Delivery {delivery.id.slice(0, 8)}</strong><span className="badge status-failed">Failed</span></div><p className="muted small">Order {delivery.order_id}</p></div>)}
            {exceptions.length === 0 && <div className="panel muted">No failed deliveries.</div>}
          </div>
        </section>
        <section className="section">
          <h2 className="subhead">Refunds &amp; cancellations</h2>
          <div className="stack">
            {orders.filter(order => order.status === 'cancelled' || order.payment_status === 'refunded').map(order => <div className="panel" key={order.id}><div className="row space"><div><strong>{order.order_number}</strong><p className="muted small">Order: {label(order.status)}</p></div><span className="badge">Payment: {label(order.payment_status)}</span></div></div>)}
            {!orders.some(order => order.status === 'cancelled' || order.payment_status === 'refunded') && <div className="panel muted">No cancellation or refund exceptions.</div>}
          </div>
        </section>
      </>}
    </main>
  </>;
}
