'use client';

import {FormEvent,useEffect,useRef,useState} from 'react';
import {LifeBuoy} from 'lucide-react';
import {gaonApi,SupportMessage,SupportTicket} from '@/lib/api';
import {Nav} from '@/components/Nav';

const PAGE_SIZE=100;
const statusLabel=(value:string)=>value==='waiting_customer'?'Waiting for requester':value.replaceAll('_',' ');
type ReplyDraft={body:string;idempotencyKey:string|null};

export default function Support(){
  const[orderId,setOrderId]=useState('');
  const[description,setDescription]=useState('');
  const[rows,setRows]=useState<SupportTicket[]>([]);
  const[selected,setSelected]=useState<SupportTicket|null>(null);
  const[messages,setMessages]=useState<SupportMessage[]>([]);
  const[hasMore,setHasMore]=useState(false);
  const[drafts,setDrafts]=useState<Record<string,ReplyDraft>>({});
  const[msg,setMsg]=useState('');
  const[listError,setListError]=useState('');
  const[detailError,setDetailError]=useState('');
  const[threadError,setThreadError]=useState('');
  const[loadingDetail,setLoadingDetail]=useState(false);
  const[loadingThread,setLoadingThread]=useState(false);
  const[listLoading,setListLoading]=useState(true);
  const[creating,setCreating]=useState(false);
  const[replying,setReplying]=useState(false);
  const[loadingMore,setLoadingMore]=useState(false);
  const listSequence=useRef(0);
  const threadSequence=useRef(0);
  const draft=selected?drafts[selected.id]||{body:'',idempotencyKey:null}:{body:'',idempotencyKey:null};

  useEffect(()=>{
    setOrderId(new URLSearchParams(location.search).get('order_id')||'');
    load();
    return()=>{listSequence.current+=1;threadSequence.current+=1};
  },[]);

  async function load(){
    const sequence=++listSequence.current;setListLoading(true);setListError('');
    try{
      const nextRows=await gaonApi.supportTickets();
      if(sequence!==listSequence.current)return;
      setRows(nextRows);
      setSelected(current=>current?nextRows.find(row=>row.id===current.id)||current:current);
      setMsg('');
    }catch(error:any){if(sequence===listSequence.current)setListError(error.message)}
    finally{if(sequence===listSequence.current)setListLoading(false)}
  }

  async function openTicket(ticket:SupportTicket){
    const sequence=++threadSequence.current;
    setSelected(ticket);setMessages([]);setHasMore(false);setLoadingDetail(true);setLoadingThread(true);setDetailError('');setThreadError('');setMsg('');
    gaonApi.supportTicket(ticket.id).then(detail=>{if(sequence===threadSequence.current)setSelected(detail)}).catch((error:any)=>{if(sequence===threadSequence.current)setDetailError(error.message)}).finally(()=>{if(sequence===threadSequence.current)setLoadingDetail(false)});
    gaonApi.supportMessages(ticket.id,PAGE_SIZE,0).then(thread=>{if(sequence!==threadSequence.current)return;setMessages(thread);setHasMore(thread.length===PAGE_SIZE)}).catch((error:any)=>{if(sequence===threadSequence.current)setThreadError(error.message)}).finally(()=>{if(sequence===threadSequence.current)setLoadingThread(false)});
  }

  async function more(){
    if(!selected)return;
    const sequence=threadSequence.current;
    setLoadingMore(true);
    try{
      const next=await gaonApi.supportMessages(selected.id,PAGE_SIZE,messages.length);
      if(sequence!==threadSequence.current)return;
      setMessages(current=>[...current,...next]);setHasMore(next.length===PAGE_SIZE);
    }catch(error:any){if(sequence===threadSequence.current)setMsg(error.message)}
    finally{setLoadingMore(false)}
  }

  async function submit(event:FormEvent){
    event.preventDefault();setCreating(true);
    try{
      const created=await gaonApi.createSupportTicket({subject:'Order support',description,order_id:orderId||null});
      setDescription('');await load();await openTicket(created);
    }catch(error:any){setMsg(error.message)}finally{setCreating(false)}
  }

  async function reply(event:FormEvent){
    event.preventDefault();
    if(!selected||!draft.body.trim())return;
    const ticketId=selected.id;
    const sequence=threadSequence.current;
    const key=draft.idempotencyKey||crypto.randomUUID();
    setDrafts(current=>({...current,[ticketId]:{body:draft.body,idempotencyKey:key}}));
    setReplying(true);
    try{
      const sent=await gaonApi.replyToSupportTicket(ticketId,{body:draft.body,idempotency_key:key});
      setDrafts(current=>current[ticketId]?.body===draft.body&&current[ticketId]?.idempotencyKey===key?{...current,[ticketId]:{body:'',idempotencyKey:null}}:current);
      if(sequence!==threadSequence.current)return;
      if(!hasMore)setMessages(current=>current.some(item=>item.id===sent.id)?current:[...current,sent]);
      else setMsg('Reply sent. Load remaining messages to view the latest conversation.');
      await load();
      const detail=await gaonApi.supportTicket(ticketId);
      if(sequence===threadSequence.current)setSelected(detail);
    }catch(error:any){if(sequence===threadSequence.current)setMsg(error.message)}
    finally{setReplying(false)}
  }

  function changeDraft(value:string){
    if(!selected)return;
    setDrafts(current=>({...current,[selected.id]:{body:value,idempotencyKey:null}}));
  }

  return <><Nav/><main className="container section">
    <div className="sectionHead"><div><span className="eyebrow">Customer support</span><h2>Get help</h2><p className="muted">Tickets are ownership-checked. Support cannot bypass order or payment rules.</p></div></div>
    {msg&&<div className="notice" role="alert">{msg}</div>}
    <div className="splitGrid"><div className="stack">
      <form className="panel form" onSubmit={submit}><h3><LifeBuoy size={18}/> New ticket</h3><label className="field">Order reference<input value={orderId} onChange={event=>setOrderId(event.target.value)} placeholder="Optional order ID"/></label><label className="field">What happened?<textarea required minLength={5} maxLength={5000} value={description} onChange={event=>setDescription(event.target.value)}/></label><button className="btn" disabled={creating}>{creating?'Creating…':'Create ticket'}</button></form>
      <section className="panel" aria-busy={listLoading}><div className="row space"><h3>Your tickets</h3>{listError&&<button type="button" className="btn secondary" onClick={load}>Retry</button>}</div>{listError&&<div className="notice" role="alert">Tickets unavailable. {listError}</div>}{listLoading?<p className="muted">Loading tickets…</p>:<div className="stack">{rows.map(ticket=><button type="button" className="card" key={ticket.id} aria-pressed={selected?.id===ticket.id} onClick={()=>openTicket(ticket)}><strong>{ticket.subject}</strong><div className="muted small">{ticket.category} • {ticket.priority} • {statusLabel(ticket.status)}</div>{ticket.resolution_notes&&<div className="notice">{ticket.resolution_notes}</div>}</button>)}{!listError&&!rows.length&&<p className="muted">No support tickets yet.</p>}</div>}</section>
    </div><section className="panel" aria-busy={loadingDetail||loadingThread}><h3>Conversation</h3>
      {!selected&&<p className="muted">Select a ticket to read its conversation.</p>}
      {selected&&<><p><strong>{selected.subject}</strong></p>{loadingDetail?<p className="muted">Loading ticket details…</p>:<><p className="muted small">{statusLabel(selected.status)} • {selected.requester_type||'Historical requester'}</p><p>{selected.description}</p></>}{detailError&&<div className="notice" role="alert">Ticket detail unavailable. {detailError}<button type="button" className="btn secondary" onClick={()=>openTicket(selected)}>Retry</button></div>}{threadError&&<div className="notice" role="alert">Conversation unavailable. {threadError}<button type="button" className="btn secondary" onClick={()=>openTicket(selected)}>Retry</button></div>}{loadingThread?<p className="muted">Loading conversation…</p>:<div className="stack" aria-live="polite">{messages.map(message=><article className="card" key={message.id}><strong>{message.author_type==='admin'?'GaonOne support':'You'}</strong><time className="muted small" dateTime={message.created_at}>{new Date(message.created_at).toLocaleString()}</time><p>{message.body}</p></article>)}{!threadError&&!messages.length&&<p className="muted">No replies yet.</p>}{hasMore&&<button type="button" className="btn secondary" disabled={loadingMore} onClick={more}>{loadingMore?'Loading…':'Load more messages'}</button>}</div>}<form className="form" onSubmit={reply}><label className="field">Reply<textarea required minLength={1} maxLength={5000} value={draft.body} onChange={event=>changeDraft(event.target.value)} disabled={selected.status==='closed'}/></label><button className="btn" disabled={replying||selected.status==='closed'||!draft.body.trim()}>{replying?'Sending…':selected.status==='closed'?'Ticket closed':'Send reply'}</button></form></>}
    </section></div>
  </main></>;
}
