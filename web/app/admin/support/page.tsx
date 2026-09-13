'use client';

import {FormEvent,useEffect,useMemo,useRef,useState} from 'react';
import {AdminSupportTicket,gaonApi,InternalSupportMessage,SupportMessage,SupportStatus,User} from '@/lib/api';
import {Nav} from '@/components/Nav';

const PAGE_SIZE=100;
const USER_PAGE_SIZE=500;
const transitions:Record<SupportStatus,SupportStatus[]>={open:['in_progress','waiting_customer','resolved','closed'],in_progress:['waiting_customer','resolved','closed'],waiting_customer:['in_progress','resolved','closed'],resolved:['in_progress','closed'],closed:['open']};
const label=(value:string)=>value==='waiting_customer'?'Waiting for requester':value.replaceAll('_',' ').replace(/\b\w/g,char=>char.toUpperCase());
const timestamp=(value:string)=>new Date(value).toLocaleString();
type Draft={body:string;key:string|null};
type RegionErrors={queue:string;assignees:string;detail:string;public:string;internal:string};
const emptyErrors:RegionErrors={queue:'',assignees:'',detail:'',public:'',internal:''};

export default function AdminSupport(){
  const[rows,setRows]=useState<AdminSupportTicket[]>([]);
  const[users,setUsers]=useState<User[]>([]);
  const[selected,setSelected]=useState<AdminSupportTicket|null>(null);
  const[publicMessages,setPublicMessages]=useState<SupportMessage[]>([]);
  const[internalMessages,setInternalMessages]=useState<InternalSupportMessage[]>([]);
  const[publicMore,setPublicMore]=useState(false);
  const[internalMore,setInternalMore]=useState(false);
  const[drafts,setDrafts]=useState<Record<string,Draft>>({});
  const[errors,setErrors]=useState<RegionErrors>(emptyErrors);
  const[notice,setNotice]=useState('');
  const[busy,setBusy]=useState('');
  const[loading,setLoading]=useState({queue:false,assignees:false,detail:false,public:false,internal:false});
  const[capabilities,setCapabilities]=useState<string[]|null>(null);
  const[capabilityError,setCapabilityError]=useState('');
  const[capabilityLoading,setCapabilityLoading]=useState(true);
  const[accessDenied,setAccessDenied]=useState(false);
  const capabilitySequence=useRef(0);
  const listSequence=useRef(0);
  const detailSequence=useRef(0);
  const assigneeSequence=useRef(0);
  const assignees=useMemo(()=>users.filter(user=>user.role==='admin'&&user.is_active&&user.is_verified),[users]);
  const operationBusy=Boolean(busy);
  const canManageSupport=capabilities?.includes('support.manage')===true;
  const canReadUsers=capabilities?.includes('user.read')===true;
  const publicDraft=selected?drafts[`${selected.id}:public`]||{body:'',key:null}:{body:'',key:null};
  const internalDraft=selected?drafts[`${selected.id}:internal`]||{body:'',key:null}:{body:'',key:null};

  useEffect(()=>{loadCapabilities();return()=>{capabilitySequence.current+=1;listSequence.current+=1;detailSequence.current+=1;assigneeSequence.current+=1}},[]);

  async function loadCapabilities(){
    const sequence=++capabilitySequence.current;listSequence.current+=1;detailSequence.current+=1;assigneeSequence.current+=1;setCapabilityLoading(true);setCapabilityError('');setCapabilities(null);setAccessDenied(false);setSelected(null);setRows([]);setUsers([]);setPublicMessages([]);setInternalMessages([]);
    try{const response=await gaonApi.capabilities();if(sequence!==capabilitySequence.current)return;setCapabilities(response.capabilities);if(!response.capabilities.includes('support.manage')){setAccessDenied(true);return}loadQueue();if(response.capabilities.includes('user.read'))loadAssignees();else setErrors(current=>({...current,assignees:'Administrator assignment requires user.read access.'}))}
    catch(error:any){if(sequence===capabilitySequence.current){setCapabilityError(error.message);setAccessDenied(true)}}
    finally{if(sequence===capabilitySequence.current)setCapabilityLoading(false)}
  }

  function supportFailure(error:any,region:keyof RegionErrors){
    if(error?.status===403){listSequence.current+=1;detailSequence.current+=1;assigneeSequence.current+=1;setAccessDenied(true);setSelected(null);setRows([]);setUsers([]);setPublicMessages([]);setInternalMessages([]);setDrafts({});setLoading({queue:false,assignees:false,detail:false,public:false,internal:false})}
    setErrors(current=>({...current,[region]:error.message}));
  }

  async function loadQueue(){
    if(capabilities!==null&&!canManageSupport)return;
    const sequence=++listSequence.current;setLoading(current=>({...current,queue:true}));setErrors(current=>({...current,queue:''}));
    try{const next=await gaonApi.adminSupportTickets();if(sequence!==listSequence.current)return;setRows(next);setAccessDenied(false);setSelected(current=>current?next.find(row=>row.id===current.id)||current:current)}
    catch(error:any){if(sequence===listSequence.current)supportFailure(error,'queue')}
    finally{if(sequence===listSequence.current)setLoading(current=>({...current,queue:false}))}
  }

  async function loadAssignees(){
    if(capabilities!==null&&!canReadUsers)return;
    const sequence=++assigneeSequence.current;
    setLoading(current=>({...current,assignees:true}));setErrors(current=>({...current,assignees:''}));
    try{const found:User[]=[];for(let offset=0;offset<10000;offset+=USER_PAGE_SIZE){const page=await gaonApi.adminUsers(USER_PAGE_SIZE,offset);if(sequence!==assigneeSequence.current)return;found.push(...page);if(page.length<USER_PAGE_SIZE)break}if(sequence===assigneeSequence.current)setUsers(found)}
    catch(error:any){if(sequence===assigneeSequence.current){setUsers([]);setErrors(current=>({...current,assignees:error.message}))}}
    finally{if(sequence===assigneeSequence.current)setLoading(current=>({...current,assignees:false}))}
  }

  function openTicket(ticket:AdminSupportTicket){
    if(!canManageSupport||accessDenied)return;
    const sequence=++detailSequence.current;setSelected(ticket);setPublicMessages([]);setInternalMessages([]);setPublicMore(false);setInternalMore(false);setNotice('');setErrors(current=>({...current,detail:'',public:'',internal:''}));setLoading(current=>({...current,detail:true,public:true,internal:true}));
    gaonApi.adminSupportTicket(ticket.id).then(detail=>{if(sequence===detailSequence.current)setSelected(detail)}).catch(error=>{if(sequence===detailSequence.current)supportFailure(error,'detail')}).finally(()=>{if(sequence===detailSequence.current)setLoading(current=>({...current,detail:false}))});
    gaonApi.adminSupportMessages(ticket.id,'public',PAGE_SIZE,0).then(thread=>{if(sequence!==detailSequence.current)return;setPublicMessages(thread as SupportMessage[]);setPublicMore(thread.length===PAGE_SIZE)}).catch(error=>{if(sequence===detailSequence.current)supportFailure(error,'public')}).finally(()=>{if(sequence===detailSequence.current)setLoading(current=>({...current,public:false}))});
    gaonApi.adminSupportMessages(ticket.id,'internal',PAGE_SIZE,0).then(thread=>{if(sequence!==detailSequence.current)return;setInternalMessages(thread as InternalSupportMessage[]);setInternalMore(thread.length===PAGE_SIZE)}).catch(error=>{if(sequence===detailSequence.current)supportFailure(error,'internal')}).finally(()=>{if(sequence===detailSequence.current)setLoading(current=>({...current,internal:false}))});
  }

  async function loadMore(visibility:'public'|'internal'){
    if(!canManageSupport||accessDenied||!selected||operationBusy)return;const sequence=detailSequence.current;setBusy(`more-${visibility}`);setErrors(current=>({...current,[visibility]:''}));
    try{const current=visibility==='public'?publicMessages:internalMessages;const next=await gaonApi.adminSupportMessages(selected.id,visibility,PAGE_SIZE,current.length);if(sequence!==detailSequence.current)return;if(visibility==='public'){setPublicMessages(rows=>[...rows,...next as SupportMessage[]]);setPublicMore(next.length===PAGE_SIZE)}else{setInternalMessages(rows=>[...rows,...next as InternalSupportMessage[]]);setInternalMore(next.length===PAGE_SIZE)}}
    catch(error:any){if(sequence===detailSequence.current)supportFailure(error,visibility)}finally{setBusy(current=>current===`more-${visibility}`?'':current)}
  }

  function applyMutation(ticket:AdminSupportTicket,sequence:number){setRows(current=>current.map(row=>row.id===ticket.id?ticket:row));if(sequence===detailSequence.current)setSelected(ticket)}

  async function updateStatus(status:SupportStatus){
    if(!canManageSupport||accessDenied||!selected||operationBusy)return;const ticket=selected;const sequence=detailSequence.current;setBusy('status');
    try{applyMutation(await gaonApi.updateSupportTicket(ticket.id,{status,expected_version:ticket.version}),sequence);if(sequence===detailSequence.current)setNotice('Ticket status updated.')}
    catch(error:any){if(sequence===detailSequence.current){setNotice(error.status===409?'Ticket changed. Refreshing the latest state.':error.message);if(error.status===409)openTicket(ticket);else supportFailure(error,'detail')}}finally{setBusy(current=>current==='status'?'':current)}
  }

  async function assign(assigned_admin_id:string){
    if(!canManageSupport||!canReadUsers||accessDenied||!selected||operationBusy)return;const ticket=selected;const sequence=detailSequence.current;setBusy('assignment');
    try{applyMutation(await gaonApi.assignSupportTicket(ticket.id,{assigned_admin_id:assigned_admin_id||null,expected_version:ticket.version}),sequence);if(sequence===detailSequence.current)setNotice('Ticket assignment updated.')}
    catch(error:any){if(sequence===detailSequence.current){setNotice(error.status===409?'Ticket changed. Refreshing the latest state.':error.message);if(error.status===409)openTicket(ticket);else supportFailure(error,'detail')}}finally{setBusy(current=>current==='assignment'?'':current)}
  }

  async function send(event:FormEvent,visibility:'public'|'internal'){
    event.preventDefault();if(!canManageSupport||accessDenied||!selected||operationBusy)return;const ticket=selected;const sequence=detailSequence.current;const draft=visibility==='public'?publicDraft:internalDraft;if(!draft.body.trim())return;const key=draft.key||crypto.randomUUID();const draftId=`${ticket.id}:${visibility}`;setDrafts(current=>({...current,[draftId]:{body:draft.body,key}}));setBusy(`send-${visibility}`);
    try{const sent=visibility==='public'?await gaonApi.adminReplyToSupportTicket(ticket.id,{body:draft.body,idempotency_key:key}):await gaonApi.addSupportInternalNote(ticket.id,{body:draft.body,idempotency_key:key});setDrafts(current=>({...current,[draftId]:{body:'',key:null}}));if(sequence!==detailSequence.current)return;if(visibility==='public'&&!publicMore)setPublicMessages(current=>current.some(item=>item.id===sent.id)?current:[...current,sent]);if(visibility==='internal'&&!internalMore)setInternalMessages(current=>current.some(item=>item.id===sent.id)?current:[...current,sent as InternalSupportMessage]);setNotice(visibility==='public'?'Reply sent to requester.':'Internal note saved for staff only.');const detail=await gaonApi.adminSupportTicket(ticket.id);applyMutation(detail,sequence)}
    catch(error:any){if(sequence===detailSequence.current)supportFailure(error,visibility)}finally{setBusy(current=>current===`send-${visibility}`?'':current)}
  }

  function setDraft(visibility:'public'|'internal',body:string){if(!selected)return;setDrafts(current=>({...current,[`${selected.id}:${visibility}`]:{body,key:null}}))}

  return <><Nav/><main className="container section"><span className="eyebrow">Support operations</span><h2>Support queue</h2><p className="muted">Public replies are visible to requesters. Internal notes stay staff-only.</p>{notice&&<div className="notice" role="status">{notice}</div>}{capabilityLoading&&<p className="muted" role="status">Checking support access…</p>}{capabilityError&&<div className="notice" role="alert">Unable to verify support access. {capabilityError}<button type="button" className="btn secondary" onClick={loadCapabilities}>Retry access check</button></div>}{!capabilityLoading&&!capabilityError&&accessDenied&&<div className="notice" role="alert">Support access is not available for this account.</div>}{canManageSupport&&!accessDenied&&<div className="splitGrid">
    <section className="panel" aria-busy={loading.queue}><div className="row space"><h3>Tickets</h3><button type="button" className="btn secondary" disabled={loading.queue} onClick={loadQueue}>Retry queue</button></div>{errors.queue&&<div className="notice" role="alert">{errors.queue}</div>}{loading.queue?<p className="muted">Loading tickets…</p>:<div className="stack">{rows.map(ticket=><button type="button" className="card" key={ticket.id} aria-pressed={selected?.id===ticket.id} onClick={()=>openTicket(ticket)}><div className="row space"><strong>{ticket.subject}</strong><span className="badge">{ticket.priority}</span></div><p className="muted small">{label(ticket.requester_type||'historical requester')} • {label(ticket.status)}</p><p>{ticket.description}</p></button>)}{!errors.queue&&!rows.length&&<p className="muted">No support tickets.</p>}</div>}</section>
    <section className="panel"><h3>Ticket workspace</h3>{!selected&&!accessDenied&&<p className="muted">Select a ticket to review it.</p>}{selected&&<><p><strong>{selected.subject}</strong></p>{loading.detail?<p className="muted">Loading ticket details…</p>:<><p className="muted small">{selected.category} • {selected.suggested_action}</p>{errors.detail&&<div className="notice" role="alert">{errors.detail}<button type="button" className="btn secondary" onClick={()=>openTicket(selected)}>Retry ticket</button></div>}<label className="field">Assigned administrator<select aria-label="Assigned administrator" value={selected.assigned_admin_id||''} disabled={!canReadUsers||operationBusy||loading.assignees||Boolean(errors.assignees)||Boolean(errors.detail)} onChange={event=>assign(event.target.value)}><option value="">Unassigned</option>{assignees.map(user=><option key={user.id} value={user.id}>{user.full_name||user.phone}</option>)}</select></label>{errors.assignees&&<div className="notice" role="alert">Assignee list unavailable. {errors.assignees}{canReadUsers&&<button type="button" className="btn secondary" onClick={loadAssignees}>Retry assignees</button>}</div>}<div className="row space"><span className="badge">{label(selected.status)}</span>{transitions[selected.status].map(status=><button type="button" className="btn secondary" key={status} disabled={operationBusy||Boolean(errors.detail)} onClick={()=>updateStatus(status)}>{label(status)}</button>)}</div></>}
      <div className="splitGrid"><section aria-busy={loading.public}><h3>Reply to requester</h3>{errors.public&&<div className="notice" role="alert">{errors.public}<button type="button" className="btn secondary" onClick={()=>openTicket(selected)}>Retry public messages</button></div>}{loading.public?<p className="muted">Loading public conversation…</p>:<div className="stack">{publicMessages.map(message=><article className="card" key={message.id}><strong>{label(message.author_type)}</strong><time className="muted small" dateTime={message.created_at}>{timestamp(message.created_at)}</time><p>{message.body}</p></article>)}{!errors.public&&!publicMessages.length&&<p className="muted">No public replies yet.</p>}{publicMore&&<button type="button" className="btn secondary" disabled={operationBusy} onClick={()=>loadMore('public')}>Load more public messages</button>}</div>}<form className="form" onSubmit={event=>send(event,'public')}><label className="field">Public reply<textarea aria-describedby="public-help" required maxLength={5000} value={publicDraft.body} disabled={selected.status==='closed'||operationBusy} onChange={event=>setDraft('public',event.target.value)}/></label><p id="public-help" className="muted small">The requester will see this message and receive a notification.</p><button className="btn" disabled={operationBusy||selected.status==='closed'||!publicDraft.body.trim()}>{busy==='send-public'?'Sending…':selected.status==='closed'?'Ticket closed':'Send public reply'}</button></form></section>
      <section aria-busy={loading.internal}><h3>Internal — staff only</h3>{errors.internal&&<div className="notice" role="alert">{errors.internal}<button type="button" className="btn secondary" onClick={()=>openTicket(selected)}>Retry internal notes</button></div>}{loading.internal?<p className="muted">Loading internal notes…</p>:<div className="stack">{internalMessages.map(message=><article className="card" key={message.id}><strong>Internal note</strong><time className="muted small" dateTime={message.created_at}>{timestamp(message.created_at)}</time><p>{message.body}</p></article>)}{!errors.internal&&!internalMessages.length&&<p className="muted">No internal notes yet.</p>}{internalMore&&<button type="button" className="btn secondary" disabled={operationBusy} onClick={()=>loadMore('internal')}>Load more internal notes</button>}</div>}<form className="form" onSubmit={event=>send(event,'internal')}><label className="field">Internal note<textarea aria-describedby="internal-help" required maxLength={5000} value={internalDraft.body} disabled={operationBusy} onChange={event=>setDraft('internal',event.target.value)}/></label><p id="internal-help" className="muted small">Only authorized support staff can read this note.</p><button className="btn secondary" disabled={operationBusy||!internalDraft.body.trim()}>{busy==='send-internal'?'Saving…':'Save internal note'}</button></form></section></div></>}
    </section></div>}</main></>;
}
