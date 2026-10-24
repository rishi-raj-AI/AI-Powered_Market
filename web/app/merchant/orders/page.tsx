'use client';
import {useEffect, useRef, useState} from 'react';
import {PackageCheck, RefreshCw, Store} from 'lucide-react';
import {ApiError, gaonApi, Order} from '@/lib/api';
import {Nav} from '@/components/Nav';
import {Button} from '@/components/ui/Button';
import {Empty, Loading, Notice} from '@/components/ui/Feedback';

const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, character => character.toUpperCase());
const next: Record<string, string | undefined> = {placed: 'accepted', accepted: 'preparing', preparing: 'ready'};
const failureText = (error: unknown) => error instanceof Error ? error.message : 'The order action could not be confirmed.';

export default function MerchantOrders() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  const [message, setMessage] = useState<{tone: 'success' | 'warning' | 'error'; text: string} | null>(null);
  const actionLock = useRef(false);

  async function readOrders() {
    const latest = await gaonApi.merchantOrders();
    setOrders(latest);
    setLoaded(true);
    setLoadFailed(false);
    setNeedsRefresh(false);
  }
  async function refresh() {
    if (actionLock.current) return;
    actionLock.current = true;
    setBusy(true);
    try {
      await readOrders();
      setMessage(null);
    } catch (error) {
      setLoadFailed(true);
      setNeedsRefresh(true);
      setMessage({tone: 'error', text: `${failureText(error)} Refresh before another order action.`});
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }
  useEffect(() => { void refresh(); }, []);

  async function advance(order: Order) {
    const status = next[order.status];
    if (!status || actionLock.current || needsRefresh) return;
    actionLock.current = true;
    setBusy(true);
    setMessage(null);
    try {
      const updated = await gaonApi.updateMerchantOrder(order.id, status);
      setOrders(current => current.map(item => item.id === order.id ? updated : item));
      setMessage({tone: 'success', text: `Order ${order.order_number} moved to ${label(status)}.`});
    } catch (error) {
      const uncertain = !(error instanceof ApiError) || error.status >= 500;
      if (uncertain) {
        setNeedsRefresh(true);
        try {
          await readOrders();
          setMessage({tone: 'warning', text: 'The order response was not confirmed. Latest order status is shown; review it before another action.'});
        } catch {
          setLoadFailed(true);
          setMessage({tone: 'error', text: 'Could not confirm this order status. Refresh before another order action.'});
        }
      } else {
        setMessage({tone: 'error', text: failureText(error)});
      }
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }

  const active = orders.filter(order => !['delivered', 'cancelled'].includes(order.status));
  return <>
    <Nav/>
    <main className="container section">
      <div className="sectionHead">
        <div>
          <span className="eyebrow">Merchant operations</span>
          <h2>Order preparation</h2>
          <p className="muted">Accept, prepare and mark orders ready using backend-controlled transitions.</p>
        </div>
        <Button intent="secondary" disabled={busy} onClick={refresh}><RefreshCw size={16}/>Refresh</Button>
      </div>
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
      {!loaded && !loadFailed && <Loading label="Loading merchant orders…"/>}
      <div className="statsGrid">
        <div className="card statCard"><Store/><span className="statValue">{active.length}</span><strong>Active orders</strong></div>
        <div className="card statCard"><PackageCheck/><span className="statValue">{orders.filter(order => order.status === 'ready').length}</span><strong>Ready for rider</strong></div>
      </div>
      <div className="stack">
        {active.map(order => {
          const target = next[order.status];
          return <section className="panel" key={order.id} aria-label={`Order ${order.order_number}`}>
            <div className="row space">
              <div><span className="eyebrow">{order.order_number}</span><h3>{label(order.status)}</h3><p className="muted small">Payment: {order.payment_method.toUpperCase()} · {label(order.payment_status)}</p></div>
              {target
                ? <Button disabled={busy || needsRefresh} onClick={() => advance(order)}>{target === 'accepted' ? 'Accept order' : target === 'preparing' ? 'Start preparing' : 'Mark ready'}</Button>
                : <span className={`badge status-${order.status}`}>{label(order.status)}</span>}
            </div>
          </section>;
        })}
        {loaded && !loadFailed && active.length === 0 && <Empty title="No active orders" explanation="New customer orders will appear here."/>}
      </div>
    </main>
  </>;
}
