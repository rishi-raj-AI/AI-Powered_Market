'use client';
import {useEffect, useRef, useState} from 'react';
import {api, ApiError, gaonApi, DeliveryTask} from '@/lib/api';
import {Nav} from '@/components/Nav';
import {Button} from '@/components/ui/Button';
import {FormField} from '@/components/ui/FormField';
import {Empty, Loading, Notice} from '@/components/ui/Feedback';

const money = (value: string | number) => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'}).format(Number(value));
type Action = 'pickup' | 'challenge' | 'verify' | 'collect' | 'complete';
type Message = {text: string; tone: 'success' | 'warning' | 'error'};
const errorMessage = (error: unknown) => error instanceof Error ? error.message : 'The request could not be confirmed.';

export default function DeliveryComplete() {
  const [tasks, setTasks] = useState<DeliveryTask[]>([]);
  const [otp, setOtp] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<Message | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [needsRefresh, setNeedsRefresh] = useState(false);
  // These guards take effect before React renders disabled controls. Refresh
  // shares the same guard so an older task list cannot replace a mutation result.
  const inFlight = useRef(false);
  const refreshRequired = useRef(false);

  function requireRefresh() {
    refreshRequired.current = true;
    setNeedsRefresh(true);
  }

  async function readTasks() {
    const latest = await gaonApi.myDeliveryTasks();
    setTasks(latest);
    setLoaded(true);
    setLoadFailed(false);
    refreshRequired.current = false;
    setNeedsRefresh(false);
  }

  async function refresh() {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    try {
      await readTasks();
      setMessage(null);
    } catch (error) {
      requireRefresh();
      setLoadFailed(true);
      setMessage({tone: 'error', text: `${errorMessage(error)} Refresh before another action.`});
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  useEffect(() => { void refresh(); }, []);

  async function perform(task: DeliveryTask, action: Action) {
    if (inFlight.current || refreshRequired.current) return;
    if (action === 'verify' && !/^\d{6}$/.test(otp[task.id] || '')) return;
    inFlight.current = true;
    setBusy(true);
    setMessage(null);
    let acknowledged = false;
    try {
      const path = `/delivery/${task.id}`;
      let text: string;
      switch (action) {
        case 'pickup':
          await gaonApi.updateDelivery(task.id, 'picked_up');
          text = 'Pickup confirmed.';
          break;
        case 'challenge':
          await api(`${path}/proof/challenge`, {method: 'POST'});
          text = 'Verification code sent to the customer. Ask for it only after handover.';
          break;
        case 'verify':
          await api(`${path}/proof`, {method: 'POST', body: JSON.stringify({otp: otp[task.id]})});
          text = 'Proof of delivery verified.';
          break;
        case 'collect':
          await api(`${path}/cod-collection`, {method: 'POST', body: JSON.stringify({amount: task.total})});
          text = `COD ${money(task.total)} recorded.`;
          break;
        case 'complete':
          await api(`${path}/complete`, {method: 'POST'});
          text = 'Delivery completed through the guarded completion endpoint.';
          break;
      }
      acknowledged = true;
      if (action === 'pickup' || action === 'complete') {
        requireRefresh();
        await readTasks();
      }
      setMessage({tone: 'success', text});
    } catch (error) {
      const uncertain = !(error instanceof ApiError) || error.status >= 500;
      if (!acknowledged && action === 'complete' && uncertain) {
        // A failed response is not proof that completion failed. Read server
        // state before allowing another action; never replay the mutation here.
        requireRefresh();
        try {
          await readTasks();
          setMessage({tone: 'warning', text: 'The completion response was not confirmed. Latest delivery status is shown; review it before another action.'});
        } catch {
          setLoadFailed(true);
          setMessage({tone: 'error', text: 'Could not confirm delivery status. Refresh before another action.'});
        }
      } else if (acknowledged) {
        setLoadFailed(true);
        setMessage({tone: 'warning', text: 'The action was recorded, but delivery status could not be refreshed. Refresh before another action.'});
      } else {
        setMessage({tone: 'error', text: errorMessage(error)});
      }
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }

  const activeTasks = tasks.filter(task => ['assigned', 'picked_up'].includes(task.status));
  const actionsDisabled = busy || needsRefresh;
  return <>
    <Nav/>
    <main className="container section">
      <div className="sectionHead">
        <div>
          <span className="eyebrow">Guarded rider flow</span>
          <h2>Pickup &amp; delivery proof</h2>
          <p className="muted">Pickup, customer OTP, COD collection and completion stay backend-authoritative.</p>
        </div>
        <Button intent="secondary" disabled={busy} onClick={refresh}>Refresh</Button>
      </div>
      {message && <Notice tone={message.tone}>{message.text}</Notice>}
      {!loaded && !loadFailed && <Loading label="Loading delivery tasks…"/>}
      <div className="stack" style={{marginTop: 12}}>
        {activeTasks.map(task => <section className="panel" key={task.id} aria-label={`Delivery ${task.order_number}`}>
          <div className="row space">
            <div style={{minWidth: 0, overflowWrap: 'anywhere'}}>
              <strong>{task.order_number}</strong>
              <p className="muted small">{task.store_name} → {task.customer_landmark}</p>
            </div>
            <span className={`badge status-${task.status}`}>{task.status.replaceAll('_', ' ')}</span>
          </div>
          {task.status === 'assigned' && <Button disabled={actionsDisabled} onClick={() => perform(task, 'pickup')}>Confirm pickup</Button>}
          {task.status === 'picked_up' && <div className="stack" style={{marginTop: 16}}>
            <Button intent="secondary" disabled={actionsDisabled} onClick={() => perform(task, 'challenge')}>Send customer OTP</Button>
            <FormField
              id={`delivery-code-${task.id}`}
              label="Customer handoff code"
              help="Ask for this code only after handing over the order."
              value={otp[task.id] || ''}
              onChange={event => setOtp(values => ({...values, [task.id]: event.target.value.replace(/\D/g, '').slice(0, 6)}))}
              placeholder="6-digit customer OTP"
              inputMode="numeric"
              autoComplete="off"
              disabled={actionsDisabled}
              style={{minWidth: 0, width: '100%'}}
            />
            <Button intent="secondary" disabled={actionsDisabled || otp[task.id]?.length !== 6} onClick={() => perform(task, 'verify')}>Verify proof</Button>
            {task.payment_method === 'cod' && task.payment_status !== 'paid' &&
              <Button intent="secondary" disabled={actionsDisabled} onClick={() => perform(task, 'collect')}>Record COD {money(task.total)}</Button>}
            <Button disabled={actionsDisabled} onClick={() => perform(task, 'complete')}>Complete delivery</Button>
            <p className="muted small">Completion will fail unless proof and, for COD, collection are already verified by the backend.</p>
          </div>}
        </section>)}
        {loaded && !loadFailed && activeTasks.length === 0 &&
          <Empty title="No active delivery to complete" explanation="Refresh to check your latest assigned tasks."/>}
      </div>
    </main>
  </>;
}
