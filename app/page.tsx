'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowRight, CalendarDays, Check, CheckCheck, ChevronLeft, ChevronRight, CircleHelp, ClipboardList, Clock3, FileText, HeartHandshake, Inbox, LayoutDashboard, LoaderCircle, LockKeyhole, LogOut, Menu, MessageSquareText, Plus, ShieldCheck, Sparkles, Users, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

type Profile = {id: number; name: string; role: string; token?: string; can_import: number; can_review: number; can_brief: number};
type Task = {id: number; source_id: number; title: string; kind: string; due_at: string | null; owner_id: number | null; accepted: number; location: string; uncertainty: string; quote: string; source_label: string; source_text: string; synthetic: number; visibility: string; status: string; version: number; change_type: string; related_task_id: number | null};
type Slot = {id: number; caregiver_id: number; start_at: string; end_at: string; note: string};
type Draft = {id: number; day: string; text: string; approved: number};
type State = {circle: {name: string}; me: Profile; caregivers: Profile[]; tasks: Task[]; availability: Slot[]; drafts: Draft[]; sources: {id: number; label: string; text: string; synthetic: number}[]; conflicts: {task_id: number; type: string; message: string}[]; audit: {id: number; action: string; target: string; created_at: string}[]; jobs: {id: string; status: string; item_count: number; error: string | null}[]};
type Health = {status: string; model: string};
type Nav = 'Overview' | 'Import inbox' | 'Review queue' | 'Responsibility board' | 'Calendar' | 'Handoffs' | 'Availability' | 'Privacy & access';
const navigation: {name: Nav; icon: typeof Inbox}[] = [
  {name: 'Overview', icon: LayoutDashboard}, {name: 'Import inbox', icon: Inbox},
  {name: 'Review queue', icon: ClipboardList}, {name: 'Responsibility board', icon: Users},
  {name: 'Calendar', icon: CalendarDays}, {name: 'Handoffs', icon: MessageSquareText},
  {name: 'Availability', icon: Clock3}, {name: 'Privacy & access', icon: ShieldCheck},
];
const descriptions: Record<Nav, string> = {
  Overview: 'The whole picture. A little less on your mind.',
  'Import inbox': 'Bring the scattered pieces into one place.',
  'Review queue': 'A suggestion becomes a plan when you say so.',
  'Responsibility board': 'Clear responsibilities. Freely accepted.',
  Calendar: 'Make room for what matters this week.',
  Handoffs: 'Help the next person pick up where you left off.',
  Availability: 'Helping starts with knowing what is possible.',
  'Privacy & access': 'Shared care starts with a choice about what to share.',
};
const dayLabel = (date: string | null) => date ? new Intl.DateTimeFormat('en', {month: 'short', day: 'numeric', timeZone: 'Asia/Karachi'}).format(new Date(date)) : 'Date to confirm';
const timeLabel = (date: string | null) => date ? new Intl.DateTimeFormat('en', {hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Karachi'}).format(new Date(date)) : 'Time to confirm';
const localDate = (date: string | null) => date ? new Date(new Date(date).getTime() + 5 * 3600000).toISOString().slice(0, 16) : '';
const withOffset = (value: string) => value ? value + ':00+05:00' : null;

export default function Workspace() {
  const [token, setToken] = useState('');
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [data, setData] = useState<State | null>(null);
  const [health, setHealth] = useState<Health>({status: 'checking', model: 'ministral-3:14b'});
  const [view, setView] = useState<Nav>('Overview');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [menu, setMenu] = useState(false);
  const [access, setAccess] = useState('');
  const [day, setDay] = useState('2026-10-26');
  const [importText, setImportText] = useState('');
  const [importLabel, setImportLabel] = useState('Family messages');
  const [reference, setReference] = useState('2026-10-24T09:00');
  const [visibility, setVisibility] = useState('circle');
  const [synthetic, setSynthetic] = useState(true);
  const [jobId, setJobId] = useState('');
  const [jobProgress, setJobProgress] = useState('Your import is saved and waiting to start.');
  const [selectedDraft, setSelectedDraft] = useState<number | null>(null);
  const [approvedText, setApprovedText] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  const api = useCallback(async (path: string, options: RequestInit = {}) => {
    const response = await fetch('/api' + path, {...options,
      headers: {'Content-Type': 'application/json', ...(token ? {Authorization: 'Bearer ' + token} : {}), ...options.headers}});
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(typeof body.detail === 'string' ? body.detail : 'Please check the entered details and try again.');
    }
    return response.json();
  }, [token]);
  const refresh = useCallback(async () => { if (token) setData(await api('/state')); }, [api, token]);
  const run = async (fn: () => Promise<void>) => {
    setError(''); setNotice(''); setBusy(true);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : 'Something went wrong. Try again.'); }
    finally { setBusy(false); }
  };
  useEffect(() => {
    setToken(sessionStorage.getItem('carerelay-token') || '');
    try { setProfiles(JSON.parse(sessionStorage.getItem('carerelay-profiles') || '[]')); } catch { /* invalid stored demo state */ }
  }, []);
  useEffect(() => { refresh().catch(e => setError(e.message)); }, [refresh]);
  useEffect(() => {
    const check = () => api('/health').then(setHealth).catch(() => setHealth({status: 'offline', model: 'ministral-3:14b'}));
    check(); const timer = setInterval(check, 15000); return () => clearInterval(timer);
  }, [api]);
  useEffect(() => {
    if (!jobId && data) {
      const pending = data.jobs.find(job => job.status === 'queued' || job.status === 'processing');
      if (pending) setJobId(pending.id);
    }
  }, [data, jobId]);
  useEffect(() => {
    if (!jobId) return;
    const poll = async () => {
      try {
        const job = await api('/jobs/' + jobId);
        if (job.status === 'completed') {
          setJobId(''); setNotice(`${job.item_count} suggestions are ready for your review.`); await refresh(); setView('Review queue');
        } else if (job.status === 'failed') { setJobId(''); setError(job.error); await refresh(); }
        else setJobProgress(job.status === 'queued'
          ? 'Your import is saved and waiting for the local worker. It will start automatically when the worker is available.'
          : job.attempts > 1 ? 'Your saved import is retrying after an interruption. No need to submit it again.'
          : 'Your local model is reading the source. Suggestions will appear in the review queue.');
      } catch { setJobProgress('Connection interrupted. Your import is saved; progress will reconnect automatically.'); }
    };
    const timer = setInterval(poll, 1800); poll(); return () => clearInterval(timer);
  }, [api, jobId, refresh]);
  useEffect(() => { setApprovedText(''); }, [selectedDraft, token]);
  const signIn = (value: string) => { sessionStorage.setItem('carerelay-token', value); setJobId(''); setToken(value); setData(null); setError(''); setApprovedText(''); };
  const createDemo = () => run(async () => {
    const result = await api('/demo', {method: 'POST'});
    sessionStorage.setItem('carerelay-profiles', JSON.stringify(result.profiles));
    setProfiles(result.profiles); signIn(result.profiles[0].token);
  });
  const navigate = (next: Nav) => {setView(next); setMenu(false); setError(''); setNotice('');};
  const name = (id: number | null) => data?.caregivers.find(c => c.id === id)?.name || 'Unassigned';
  const queue = data?.tasks.filter(t => t.status === 'suggested') || [];
  const active = data?.tasks.filter(t => t.status === 'confirmed') || [];
  const selected = data?.drafts.find(d => d.id === selectedDraft) || data?.drafts[0];
  const today = active.filter(t => !t.due_at || t.due_at.slice(0, 10) === day);
  const nextWeek = (delta: number) => { const d = new Date(day + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + delta); setDay(d.toISOString().slice(0, 10)); };
  const [slotStart, setSlotStart] = useState('2026-10-26T08:00');
  const [slotEnd, setSlotEnd] = useState('2026-10-26T12:00');
  const [slotNote, setSlotNote] = useState('Work shift');

  if (!token) return <main className="welcome">
    <div className="welcome-copy"><div className="brand"><span className="brand-icon"><HeartHandshake size={25}/></span>CareRelay<span className="wordmark-dot">.</span></div>
      <div className="eyebrow">FOR THE PEOPLE WHO SHOW UP</div>
      <h1>Everyone wants to help.<br/><em>Let’s make it easier.</em></h1>
      <p>Turn family messages into a shared plan, with the source behind every detail and a person behind every decision.</p>
      <div className="welcome-promise"><ShieldCheck size={20}/><span>Local AI. Private by design. Always your call.</span></div>
    </div>
    <section className="welcome-panel"><span className="tiny-tag">A FICTIONAL FAMILY. A REAL WORKFLOW.</span><h2>A little less to carry.</h2>
      <p>Meet Alex, Maya, Sam, and Robin. Help them coordinate the coming two weeks, one approved task at a time.</p>
      <div className="avatar-stack">{['A','M','S','R'].map((v,i) => <span className={'avatar color-'+i} key={v}>{v}</span>)}<small>Four people. One shared plan.</small></div>
      <Button onClick={createDemo} disabled={busy}>{busy ? <LoaderCircle className="spin" size={16}/> : <Plus size={16}/>}Create fictional care circle<ArrowRight size={16}/></Button>
      <p className="small-muted">Clearly labeled synthetic data. Nothing is sent to anyone.</p>
      <div className="divider"><span>Already have access?</span></div>
      <form onSubmit={e => {e.preventDefault(); signIn(access.trim());}}><label htmlFor="access">Caregiver access token</label><input id="access" type="password" value={access} onChange={e => setAccess(e.target.value)} required placeholder="Paste your private access token" autoComplete="off"/><Button variant="outline" type="submit" disabled={!access.trim()}>Open my workspace<ArrowRight size={15}/></Button></form>
      {error && <div className="alert error" role="alert">{error}</div>}
    </section><footer>Coordination, with care. This workspace offers no medical advice.</footer>
  </main>;

  return <div className="app-shell">
    <aside className={'sidebar ' + (menu ? 'open' : '')}>
      <a href="#main" className="brand"><span className="brand-icon"><HeartHandshake size={24}/></span>CareRelay<span className="wordmark-dot">.</span></a>
      <div className="circle-label"><span className="circle-mark">M</span><span>{data?.circle.name || 'Your care circle'}<small>Family workspace</small></span><span className="green-dot"/></div>
      <div className="nav-caption">YOUR SHARED SPACE</div>
      <nav aria-label="Main navigation">{navigation.map(({name, icon: Icon}) => <button key={name} className={'nav-link ' + (view === name ? 'selected' : '')} onClick={() => navigate(name)} aria-current={view === name ? 'page' : undefined}><Icon size={18}/><span>{name}</span>{name === 'Review queue' && queue.length > 0 && <b>{queue.length}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="privacy-note"><LockKeyhole size={17}/><div>Close to home.<small>Your messages stay on this machine.</small></div></div>
        <div className="user-row"><span className="avatar color-0">{data?.me.name[0] || '·'}</span><div><strong>{data?.me.name || 'Loading…'}</strong><small>{data?.me.role || 'Caregiver'}</small></div><button title="Sign out" aria-label="Sign out" onClick={() => {sessionStorage.removeItem('carerelay-token'); setToken(''); setData(null);}}><LogOut size={17}/></button></div>
      </div>
    </aside>
    <div className="main-shell"><header className="topbar"><button className="mobile-toggle" aria-label="Toggle navigation" onClick={() => setMenu(!menu)}><Menu size={22}/></button><div className="breadcrumb">Family workspace <span>/</span> <strong>{view}</strong></div><div className="topbar-right"><span className={'model-status ' + (health.status === 'ready' ? 'ready' : '')}><span/>{health.status === 'ready' ? 'Local AI ready' : health.status === 'model_missing' ? 'Model downloading / missing' : 'Local AI offline'}</span><span className="synthetic-pill">SYNTHETIC DEMO</span></div></header>
    <main id="main" className="main-content">
      <div className="page-heading"><div><div className="eyebrow">A LITTLE LESS TO CARRY</div><h1>{view === 'Overview' ? `Good to see you${data ? ', ' + data.me.name : ''}.` : view}</h1><p>{descriptions[view]}</p></div><div className="heading-action">{view === 'Overview' && <Button onClick={() => navigate('Import inbox')}><Plus size={16}/>Import messages</Button>}{view === 'Calendar' && <input aria-label="Calendar date" type="date" value={day} onChange={e => setDay(e.target.value)}/>}</div></div>
      {error && <div className="alert error" role="alert"><CircleHelp size={18}/>{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
      {notice && <div className="alert success" role="status"><CheckCheck size={18}/>{notice}</div>}
      {!data ? <section className="empty-state"><LoaderCircle className="spin"/><h2>Opening your circle…</h2><Button variant="outline" onClick={() => run(refresh)}>Retry connection</Button></section> : <>

      {view === 'Overview' && <>
        <section className="hero-strip"><div className="hero-illustration"><HeartHandshake size={44} strokeWidth={1.25}/><span className="orbit orbit-1"/><span className="orbit orbit-2"/></div><div><span className="tiny-tag">TOGETHER, A LITTLE LIGHTER</span><h2>Care is a team effort.<br/>The remembering can be, too.</h2><p>One place for the little things that make a big difference.</p></div><Button variant="outline" onClick={() => navigate('Handoffs')}>Prepare a handoff<ArrowRight size={16}/></Button></section>
        <section className="stats-grid" aria-label="Circle summary">{[
          {label:'To review', value:queue.length, note:'Suggestions waiting for a human check', icon:ClipboardList, color:'amber'},
          {label:'On the shared plan', value:active.length, note:'Approved tasks, visible to this profile', icon:CalendarDays, color:'teal'},
          {label:'Need a helping hand', value:active.filter(t => !t.accepted).length, note:'Still waiting for someone to accept', icon:Users, color:'rose'},
          {label:'People in your corner', value:data.caregivers.length, note:'Every person chooses how to help', icon:HeartHandshake, color:'sage'},
        ].map(s => <article className="stat" key={s.label}><div><span>{s.label}</span><span className={'stat-icon '+s.color}><s.icon size={18}/></span></div><strong>{s.value.toString().padStart(2,'0')}</strong><small>{s.note}</small></article>)}</section>
        <div className="overview-columns"><section className="panel"><div className="panel-heading"><div><div className="eyebrow">THE PLAN, AT A GLANCE</div><h2>Coming together</h2></div><Button variant="ghost" size="sm" onClick={() => navigate('Responsibility board')}>View board<ArrowRight size={15}/></Button></div>
          {active.length ? active.slice(0,4).map(t => <TaskRow key={t.id} task={t} name={name(t.owner_id)} onClick={() => navigate('Responsibility board')}/>) : <div className="empty-compact"><CalendarDays size={30}/><h3>A calmer week starts here.</h3><p>Import a few messages, review the suggestions, and your approved plan will appear here.</p><Button variant="outline" size="sm" onClick={() => navigate('Import inbox')}>Bring in the first messages<ArrowRight size={14}/></Button></div>}
        </section><section className="panel attention-panel"><div className="panel-heading"><div><div className="eyebrow">LET’S CLOSE THE LOOP</div><h2>A little attention</h2></div><span className="count-chip">{data.conflicts.length + queue.length}</span></div>
          {queue.length > 0 && <button className="attention-item" onClick={() => navigate('Review queue')}><span className="attention-icon amber"><ClipboardList size={18}/></span><div><strong>{queue.length} suggestions to check</strong><p>Look at the original message before approving.</p></div><ChevronRight size={16}/></button>}
          {data.conflicts.slice(0,3).map((c,i) => <button className="attention-item" key={i} onClick={() => navigate('Responsibility board')}><span className="attention-icon rose"><CircleHelp size={18}/></span><div><strong>Task #{c.task_id} needs a check</strong><p>{c.message}</p></div><ChevronRight size={16}/></button>)}
          {!queue.length && !data.conflicts.length && <div className="empty-compact"><ShieldCheck size={30}/><h3>No loose ends to show yet.</h3><p>We’ll flag unclaimed travel and scheduling conflicts as the plan takes shape.</p></div>}
          <div className="gentle-note"><Sparkles size={16}/><span>AI suggests. Your family decides.</span></div>
        </section></div>
        <section className="circle-section"><div><div className="eyebrow">YOUR CARE CIRCLE</div><h2>Many hands. Shared understanding.</h2></div><div className="caregiver-grid">{data.caregivers.map((c,i) => <article className="caregiver-card" key={c.id}><span className={'avatar color-'+i}>{c.name[0]}</span><div><strong>{c.name}</strong><small>{c.role}</small></div><span className="caregiver-count">{active.filter(t => t.owner_id === c.id && t.accepted).length} accepted</span></article>)}</div></section>
      </>}

      {view === 'Import inbox' && <div className="import-layout"><section className="panel import-panel"><div className="panel-heading"><div><div className="eyebrow">START WITH THE SOURCE</div><h2>What’s in the family chat?</h2></div><MessageSquareText size={22}/></div><p className="section-description">Paste messages, appointment details, or notes. CareRelay finds coordination tasks and keeps the original words beside every suggestion.</p>
        <form onSubmit={e => {e.preventDefault(); run(async () => {const result = await api('/imports', {method:'POST', body:JSON.stringify({text:importText, reference_at:withOffset(reference), label:importLabel, synthetic, visibility})}); setJobId(result.job_id); await refresh();});}}>
          <div className="field-grid"><label>Source label<input required maxLength={100} value={importLabel} onChange={e => setImportLabel(e.target.value)}/></label><label>Reference date & time (PKT)<input required type="datetime-local" value={reference} onChange={e => setReference(e.target.value)}/></label></div>
          <label htmlFor="source-text">Messages and notes</label><textarea id="source-text" className="source-input" required minLength={5} maxLength={24000} value={importText} onChange={e => setImportText(e.target.value)} placeholder={'Alex: The appointment moved to Monday at 10.\nMaya: I’m working that morning. Can someone arrange a ride?\n\nKeep original dates and names where possible.'}/>
          <div className="import-toolbar"><input ref={fileRef} type="file" accept=".txt,text/plain" hidden onChange={e => {const file=e.target.files?.[0]; if(file) run(async () => {if(file.size>48000) throw new Error('Choose a plain text file under 48 KB.'); setImportText(await file.text()); setImportLabel(file.name);});}}/><Button variant="ghost" size="sm" type="button" onClick={() => fileRef.current?.click()}><ArrowDownToLine size={15}/>Upload .txt</Button><span>{importText.length.toLocaleString()} / 24,000</span></div>
          <div className="field-grid"><label>Who can see this source?<select value={visibility} onChange={e => setVisibility(e.target.value)}><option value="circle">Everyone in this care circle</option><option value="private">Only me</option></select></label><label className="checkbox-label"><input type="checkbox" checked={synthetic} onChange={e => setSynthetic(e.target.checked)}/>This is fictional / synthetic input</label></div>
          <div className="form-footer"><span><LockKeyhole size={14}/>Processed by {health.model} on this machine</span><Button disabled={busy || !!jobId || health.status !== 'ready' || !data.me.can_import} type="submit">{jobId ? <LoaderCircle size={16} className="spin"/> : <Sparkles size={16}/>} {jobId ? 'Finding the pieces…' : 'Find coordination tasks'}</Button></div>
        </form>{jobId && <div className="processing-note" role="status">{jobProgress}</div>}
      </section><div><section className="panel demo-card"><span className="tiny-tag">TRY THE STORY</span><h2>One changed appointment.<br/>One missing ride.</h2><p>Load a short fictional family conversation, then let the local model find what needs attention.</p><Button variant="outline" onClick={() => run(async () => {const dataset = await api('/demo/messages'); setImportText(dataset.demo_text); setReference(dataset.reference_at.slice(0,16)); setSynthetic(true); setImportLabel('Morgan family · synthetic conversation');})}>Load fictional conversation<ArrowRight size={15}/></Button><small>The full labeled, two-week dataset is included in the project.</small></section>
        <section className="source-history"><div className="eyebrow">RECENT IMPORTS</div>{data.sources.length ? data.sources.slice(0,6).map(s => <div className="history-item" key={s.id}><FileText size={17}/><div><strong>{s.label}</strong><small>Source #{s.id} · {s.synthetic ? 'Synthetic input' : 'User-provided input'}</small></div></div>) : <p>Your imported sources will stay here for reference.</p>}{data.jobs.filter(j => j.status === 'failed').slice(0,2).map(j => <div className="alert error" key={j.id}>Import failed: {j.error} Submit the source again to retry.</div>)}</section>
      </div></div>}

      {view === 'Review queue' && <><div className="info-banner"><ShieldCheck size={19}/><div><strong>Nothing is assigned just because AI found it.</strong><span>Check the quote, confirm the details, then approve or reject. A caregiver still needs to accept responsibility.</span></div><span className="count-chip">{queue.length} to review</span></div>{queue.length ? <div className="review-grid">{queue.map(t => <ReviewCard key={t.id} task={t} caregivers={data.caregivers} busy={busy} canReview={!!data.me.can_review} approved={active} onSubmit={(body) => run(async () => {await api(`/tasks/${t.id}/review`, {method:'POST', body:JSON.stringify(body)}); await refresh(); setNotice(body.decision === 'approve' ? 'Added to the approved plan. Responsibility still needs consent.' : 'Suggestion rejected. The source remains available.');})}/>)}</div> : <Empty icon={ClipboardList} title="All caught up." text="New suggestions will appear here after a source is processed." action={<Button variant="outline" onClick={() => navigate('Import inbox')}>Import messages<ArrowRight size={15}/></Button>}/>}</>}

      {view === 'Responsibility board' && <><div className="info-banner"><Users size={20}/><div><strong>A name is a proposal. Acceptance is a commitment.</strong><span>Switch fictional profiles in Privacy & access to see how each caregiver accepts their own responsibilities.</span></div></div><div className="board">{[{title:'Needs a helping hand',items:active.filter(t => !t.accepted),color:'amber'}, {title:'Accepted & in motion',items:active.filter(t => t.accepted),color:'teal'}, {title:'Taken care of',items:data.tasks.filter(t => t.status === 'done'),color:'sage'}].map(col => <section className="board-column" key={col.title}><div className="column-heading"><span className={'column-dot '+col.color}/><h2>{col.title}</h2><b>{col.items.length}</b></div>{col.items.length ? col.items.map(t => <article className="task-card" key={t.id}><div className="task-card-top"><span className="kind">{t.kind}</span><small>#{t.id}</small></div><h3>{t.title}</h3><p><CalendarDays size={14}/>{dayLabel(t.due_at)} · {timeLabel(t.due_at)}</p>{t.location && <p>{t.location}</p>}<div className="owner-line"><span className="avatar color-0">{name(t.owner_id)[0]}</span><span>{name(t.owner_id)}<small>{t.accepted ? 'Accepted responsibility' : 'Not yet accepted'}</small></span></div>{t.uncertainty && <div className="task-warning">{t.uncertainty}</div>}{data.conflicts.filter(c => c.task_id === t.id).map((c,i) => <div className="task-warning" key={i}>{c.message}</div>)}<details><summary>View source evidence</summary><blockquote>{t.quote}</blockquote><small>{t.source_label} · source #{t.source_id}</small></details>{t.status === 'confirmed' && (!t.owner_id || t.owner_id === data.me.id) && <Button size="sm" variant={t.accepted ? 'outline' : 'default'} disabled={busy} onClick={() => run(async () => {await api(`/tasks/${t.id}/${t.accepted ? 'done' : 'accept'}`, {method:'POST'}); await refresh();})}><Check size={15}/>{t.accepted ? 'Mark done' : 'I can take this'}</Button>}</article>) : <div className="column-empty">A little breathing room.</div>}</section>)}</div>{data.tasks.some(t => t.status === 'cancelled') && <details className="panel archived"><summary>Cancelled and superseded items ({data.tasks.filter(t => t.status === 'cancelled').length})</summary>{data.tasks.filter(t => t.status === 'cancelled').map(t => <TaskRow key={t.id} task={t} name={name(t.owner_id)}/>)}</details>}</>}

      {view === 'Calendar' && <><div className="calendar-toolbar"><div><Button size="icon" variant="outline" aria-label="Previous week" onClick={() => nextWeek(-7)}><ChevronLeft size={16}/></Button><h2>Week of {dayLabel(day+'T12:00:00+05:00')}</h2><Button size="icon" variant="outline" aria-label="Next week" onClick={() => nextWeek(7)}><ChevronRight size={16}/></Button></div><span className="small-muted">All times in Pakistan Standard Time (UTC+05:00)</span></div><div className="calendar-grid">{Array.from({length:7},(_,i) => {const d = new Date(day+'T12:00:00Z'); d.setUTCDate(d.getUTCDate()+i); const key = d.toISOString().slice(0,10); const items=active.filter(t => t.due_at?.slice(0,10) === key); return <section className="calendar-day" key={key}><div className="calendar-day-title"><span>{new Intl.DateTimeFormat('en',{weekday:'short',timeZone:'UTC'}).format(d)}</span><strong>{d.getUTCDate()}</strong></div>{items.map(t => <article className={'calendar-item '+(t.accepted ? 'accepted' : '')} key={t.id}><time>{timeLabel(t.due_at)}</time><h3>{t.title}</h3><span>{name(t.owner_id)} · {t.accepted ? 'accepted' : 'unconfirmed'}</span></article>)}{!items.length && <span className="calendar-clear">No approved items</span>}</section>;})}</div>{active.some(t => !t.due_at) && <div className="alert"><CircleHelp size={18}/>{active.filter(t => !t.due_at).length} approved item(s) still need a date. Find them on the responsibility board.</div>}<section className="panel day-plan"><div className="panel-heading"><h2>Day view · {dayLabel(day+'T12:00:00+05:00')}</h2><input aria-label="Day view date" type="date" value={day} onChange={e => setDay(e.target.value)}/></div>{today.length ? today.map(t => <TaskRow key={t.id} task={t} name={name(t.owner_id)}/>) : <p>No approved items for this day.</p>}</section></>}

      {view === 'Handoffs' && <div className="handoff-layout"><section className="panel"><div className="panel-heading"><div><div className="eyebrow">PASS THE WHOLE PICTURE</div><h2>A handoff with the details attached.</h2></div><MessageSquareText size={23}/></div><p className="section-description">Start from approved shared tasks. Every line points back to its evidence; open questions stay separate from accepted commitments.</p><div className="handoff-controls"><label>Day (PKT)<input type="date" value={day} onChange={e => setDay(e.target.value)}/></label><Button disabled={busy || !data.me.can_brief || health.status !== 'ready'} onClick={() => run(async () => {const draft=await api('/drafts',{method:'POST',body:JSON.stringify({day})}); setSelectedDraft(draft.id); setApprovedText(''); await refresh();})}>{busy ? <LoaderCircle className="spin" size={16}/> : <Sparkles size={16}/>}Prepare day brief</Button></div>
        {selected ? <><div className="draft-meta"><span className="tiny-tag">{selected.approved ? 'PREVIOUSLY APPROVED · RECHECK BEFORE COPYING' : 'DRAFT · HUMAN REVIEW REQUIRED'}</span><span>#{selected.id}</span></div><pre className="handoff-text">{selected.text}</pre><div className="form-footer"><span><ShieldCheck size={15}/>Review names, times, and unresolved details.</span><Button disabled={busy} onClick={() => run(async () => {const r=await api(`/drafts/${selected.id}/approve`,{method:'POST'}); setApprovedText(r.text); await refresh(); setNotice('Handoff approved against the current plan. You can now copy it for manual sharing.');})}><CheckCheck size={16}/>Approve for manual sharing</Button></div>{approvedText && <Button variant="outline" onClick={() => run(async () => {const r=await api(`/drafts/${selected.id}/approve`,{method:'POST'}); await navigator.clipboard.writeText(r.text); setNotice('Approved handoff copied. Share it manually with the people you choose.');})}>Copy approved handoff</Button>}</> : <div className="empty-compact"><MessageSquareText size={32}/><h3>A clearer next shift.</h3><p>Approve a few shared tasks, choose their day, and prepare your first handoff.</p></div>}
      </section><aside><section className="panel demo-card"><ShieldCheck size={26}/><h2>Nothing leaves on its own.</h2><p>CareRelay never sends messages. Only you decide when a handoff is ready and who receives it.</p><p>Private sources stay out of shareable briefs. If the plan changes, prepare a fresh draft.</p></section><div className="source-history"><div className="eyebrow">YOUR RECENT DRAFTS</div>{data.drafts.map(d => <button className="history-item draft-link" key={d.id} onClick={() => {setSelectedDraft(d.id); setApprovedText('');}}><FileText size={17}/><div><strong>{d.day}</strong><small>Draft #{d.id} · {d.approved ? 'Approved' : 'Needs review'}</small></div></button>)}</div></aside></div>}

      {view === 'Availability' && <div className="import-layout"><section className="panel"><div className="panel-heading"><div><div className="eyebrow">PROTECT YOUR TIME</div><h2>When you can’t be there</h2></div><Clock3 size={22}/></div><p className="section-description">Add unavailable windows for {data.me.name}. The board flags overlaps using a one-hour planning window for each task. This is a scheduling estimate.</p><form onSubmit={e => {e.preventDefault(); run(async () => {await api('/availability',{method:'POST',body:JSON.stringify({start_at:withOffset(slotStart),end_at:withOffset(slotEnd),note:slotNote})}); await refresh(); setNotice('Availability updated. The board will flag overlapping tasks.');});}}><div className="field-grid"><label>From (PKT)<input required type="datetime-local" value={slotStart} onChange={e => setSlotStart(e.target.value)}/></label><label>Until (PKT)<input required type="datetime-local" value={slotEnd} onChange={e => setSlotEnd(e.target.value)}/></label></div><label>Short note<input value={slotNote} maxLength={160} onChange={e => setSlotNote(e.target.value)}/></label><Button disabled={busy} type="submit"><Plus size={16}/>Add unavailable time</Button></form></section><section className="panel"><div className="panel-heading"><h2>The circle’s availability</h2></div>{data.availability.map(slot => <div className="availability-item" key={slot.id}><span className="avatar color-1">{name(slot.caregiver_id)[0]}</span><div><strong>{name(slot.caregiver_id)} · {slot.note}</strong><p>{dayLabel(slot.start_at)} · {timeLabel(slot.start_at)}–{timeLabel(slot.end_at)}</p></div>{slot.caregiver_id===data.me.id && <button className="remove" aria-label={'Remove '+slot.note} onClick={() => run(async () => {await api('/availability/'+slot.id,{method:'DELETE'}); await refresh();})}><X size={16}/></button>}</div>)}</section></div>}

      {view === 'Privacy & access' && <><div className="info-banner"><LockKeyhole size={20}/><div><strong>Household membership is not universal access.</strong><span>Private sources are visible only to their importer. Shared handoffs use circle-visible evidence only.</span></div></div><div className="privacy-grid"><section className="panel"><div className="panel-heading"><h2>Caregiver permissions</h2><ShieldCheck size={22}/></div><p className="section-description">The coordinator can grant individual access to import, review, and prepare handoffs. Every caregiver accepts their own responsibilities.</p><div className="permission-table"><div className="permission-row table-heading"><span>Caregiver</span><span>Import</span><span>Review</span><span>Brief</span></div>{data.caregivers.map(c => <div className="permission-row" key={c.id}><strong>{c.name}<small>{c.role}</small></strong>{(['can_import','can_review','can_brief'] as const).map(p => <input key={p} aria-label={`${c.name} ${p.replace('can_','')}`} type="checkbox" checked={!!c[p]} disabled={busy || data.me.role!=='Coordinator' || c.id===data.me.id} onChange={e => run(async () => {await api(`/caregivers/${c.id}/permissions`,{method:'PATCH',body:JSON.stringify({can_import:!!c.can_import,can_review:!!c.can_review,can_brief:!!c.can_brief,[p]:e.target.checked})}); await refresh();})}/>)}</div>)}</div></section><section className="panel demo-card"><span className="tiny-tag">FICTIONAL DEMO ONLY</span><h2>Walk in another caregiver’s shoes.</h2><p>Switch between the four synthetic profiles to try permissions and consent. Access tokens stay in this browser tab’s session storage.</p><label>Current demo caregiver<select value={data.me.id} onChange={e => {const p=profiles.find(p => p.id===Number(e.target.value)); if(p?.token) signIn(p.token);}} disabled={!profiles.length}>{profiles.map(p => <option key={p.id} value={p.id}>{p.name} · {p.role}</option>)}</select></label><small>This demo is for fictional data on a trusted local machine. Deployment for real households requires independent authentication and encrypted storage.</small></section></div><section className="panel audit-panel"><div className="panel-heading"><h2>Your activity trail</h2><span className="small-muted">Only your own events are shown</span></div>{data.audit.map(event => <div className="audit-row" key={event.id}><span className="audit-dot"/><strong>{event.action.replaceAll('_',' ')}</strong><span>Record {event.target}</span><time>{new Date(event.created_at).toLocaleString()}</time></div>)}</section></>}
      </>}
      <footer className="workspace-footer"><span><HeartHandshake size={15}/>Care, with a little more clarity.</span><span>Organizational assistance only · PKT (UTC+05:00) · {health.model}</span></footer>
    </main></div>
  </div>;
}

function Empty({icon:Icon,title,text,action}:{icon:typeof Inbox;title:string;text:string;action?:React.ReactNode}) {
  return <section className="empty-state"><Icon size={38} strokeWidth={1.3}/><h2>{title}</h2><p>{text}</p>{action}</section>;
}
function TaskRow({task,name,onClick}:{task:Task;name:string;onClick?:()=>void}) {
  return <div className="task-row"><span className="date-square"><strong>{task.due_at ? new Date(task.due_at).getDate() : '–'}</strong><small>{task.due_at ? new Intl.DateTimeFormat('en',{month:'short'}).format(new Date(task.due_at)) : 'TBD'}</small></span><div><button className="task-title" onClick={onClick} disabled={!onClick}>{task.title}</button><small>{timeLabel(task.due_at)}{task.location ? ' · '+task.location : ''}</small></div><span className={'status-chip '+(task.accepted ? 'teal' : 'amber')}>{task.status==='cancelled' ? 'Cancelled' : task.accepted ? name+' · accepted' : name+' · awaiting consent'}</span></div>;
}
function ReviewCard({task,caregivers,approved,busy,canReview,onSubmit}:{task:Task;caregivers:Profile[];approved:Task[];busy:boolean;canReview:boolean;onSubmit:(body:Record<string,unknown>)=>void}) {
  const [title,setTitle]=useState(task.title);
  const [kind,setKind]=useState(task.kind);
  const [due,setDue]=useState(localDate(task.due_at));
  const [owner,setOwner]=useState(task.owner_id?.toString() || '');
  const [location,setLocation]=useState(task.location);
  const [uncertainty,setUncertainty]=useState(task.uncertainty);
  const [ack,setAck]=useState(false);
  const [related,setRelated]=useState(task.related_task_id?.toString() || '');
  const send=(decision:string)=>onSubmit({decision,title,kind,due_at:withOffset(due),owner_id:owner?Number(owner):null,location,uncertainty,acknowledge_uncertainty:ack,related_task_id:related?Number(related):null,version:task.version});
  return <article className="panel review-card"><div className="review-top"><span className="kind">{task.kind}</span><span className="tiny-tag">{task.change_type==='new' ? 'SUGGESTED' : task.change_type.toUpperCase()}</span><span className="small-muted">#{task.id}</span></div><label>Task title<input value={title} minLength={3} maxLength={160} onChange={e=>setTitle(e.target.value)}/></label><div className="evidence"><span className="eyebrow">THE ORIGINAL WORDS</span><blockquote>“{task.quote}”</blockquote><small><FileText size={13}/>{task.source_label} · source #{task.source_id} · {task.synthetic?'synthetic':'user-provided'} · {task.visibility}</small></div><div className="field-grid"><label>Due date & time (PKT)<input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label><label>Proposed caregiver<select value={owner} onChange={e=>setOwner(e.target.value)}><option value="">Unassigned</option>{caregivers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label></div><div className="field-grid"><label>Task category<select value={kind} onChange={e=>setKind(e.target.value)}>{["transport","errand","appointment","pickup","confirmation"].map(value=><option key={value} value={value}>{value}</option>)}</select></label><label>Location<input value={location} maxLength={200} placeholder="Not specified" onChange={e=>setLocation(e.target.value)}/></label></div>{task.change_type!=='new' && <label>Original approved task<select value={related} onChange={e=>setRelated(e.target.value)}><option value="">Choose the task this changes</option>{approved.filter(t=>t.visibility===task.visibility).map(t=><option value={t.id} key={t.id}>#{t.id} · {t.title}</option>)}</select></label>}<label>Open questions / uncertainty<textarea rows={2} maxLength={500} value={uncertainty} onChange={e=>setUncertainty(e.target.value)}/></label><label className="checkbox-label acknowledge"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/>I checked the source, date, and unresolved details. Remaining questions are recorded above.</label><div className="review-actions"><Button variant="ghost" size="sm" disabled={busy||!canReview} onClick={()=>send('reject')}><X size={15}/>Reject</Button><Button size="sm" disabled={busy||!canReview||!ack||title.trim().length<3} onClick={()=>send('approve')}><Check size={15}/>Approve suggestion</Button></div></article>;
}
