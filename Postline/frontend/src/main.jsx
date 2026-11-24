import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowUpRight, CalendarDays, Check, ChevronDown, CircleAlert, Clock3, FileText, LayoutGrid, Link2, LogOut, Plus, Send, Sparkles} from 'lucide-react';
import {api} from './api';
import './style.css';

const platforms = {facebook: 'Facebook', instagram: 'Instagram'};
const statuses = ['draft', 'scheduled', 'publishing', 'published', 'failed', 'cancelled'];
const filters = ['all', ...statuses];
const views = [
  {label: 'Overview', icon: LayoutGrid}, {label: 'Composer', icon: FileText},
  {label: 'Accounts', icon: Link2},
];
const fresh = {platform: 'facebook', account: '', caption: '', hashtags: '', media_url: '', media_path: '', media_file: null, ai_assisted: false, scheduled_at: ''};

function dateLabel(value) {
  return value ? new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'}).format(new Date(value)) : '—';
}

function toLocal(value) {
  if (!value) return '';
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function Brand() {
  return <div className="brand"><span><Send size={21}/></span>Postline</div>;
}

function ErrorText({message}) {
  return message && <p className="error" role="alert"><CircleAlert size={17}/>{message}</p>;
}

function SignIn({onSignedIn}) {
  const [register, setRegister] = useState(false);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (register) {data.password1 = data.password; delete data.password;}
    setPending(true);
    setError('');
    try {
      onSignedIn((await api(register ? 'register' : 'login', 'POST', data)).user);
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return <main className="auth">
    <div className="auth-copy"><Brand/><div><p className="eyebrow">SOCIAL MEDIA SCHEDULER</p>
      <h1>Plan ahead.<br/>Publish on time.</h1>
      <p>Write, schedule, and track your Facebook and Instagram posts in one workspace.</p></div>
      <div className="auth-channels"><span>Facebook</span><span>Instagram</span></div>
    </div>
    <div className="auth-form"><form onSubmit={submit} key={register}>
      <h2>{register ? 'Create an account' : 'Welcome back'}</h2>
      <p className="muted">{register ? 'Set up your Postline workspace.' : 'Sign in to your Postline workspace.'}</p>
      <label>Username<input name="username" autoComplete="username" required maxLength="150"/></label>
      {register && <label>Email<input name="email" type="email" autoComplete="email" required/></label>}
      <label>Password<input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} required/></label>
      {register && <label>Confirm password<input name="password2" type="password" autoComplete="new-password" required/></label>}
      <ErrorText message={error}/>
      <button className="primary" disabled={pending}>{pending ? 'Please wait…' : register ? 'Create account' : 'Sign in'}</button>
      <button className="text-button" type="button" onClick={() => {setRegister(!register); setError('');}}>
        {register ? 'Already have an account? Sign in' : 'New to Postline? Create an account'}
      </button>
    </form></div>
  </main>;
}

function Platform({name}) {
  return <span className={'platform ' + name}><span>{name === 'facebook' ? 'f' : '◎'}</span>{platforms[name]}</span>;
}

function Dashboard({posts, edit, create, cancel}) {
  const [filter, setFilter] = useState('all');
  const shown = posts.filter(post => filter === 'all' || post.status === filter);
  const next = posts.filter(post => post.status === 'scheduled').sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at))[0];
  const cards = [
    ['Scheduled', 'scheduled', CalendarDays], ['Drafts', 'draft', FileText],
    ['Published', 'published', Check], ['Failed', 'failed', CircleAlert],
  ];
  return <>
    <header className="page-heading"><div><h1>Overview</h1><p>See what’s in progress and what’s going live next.</p></div>
      <button className="primary" onClick={create}><Plus size={19}/> New post</button>
    </header>
    <section className="up-next"><div><span className="eyebrow"><Clock3 size={15}/> NEXT TO PUBLISH</span>
      <h2>{next ? next.caption.split('\n')[0] || 'Image post' : 'No posts scheduled'}</h2>
      <p>{next ? platforms[next.platform] + ' · ' + dateLabel(next.scheduled_at) : 'Choose a time in the composer to queue your first post.'}</p>
    </div><button className="light" onClick={next ? () => edit(next) : create}>{next ? 'View post' : 'Open composer'}<ArrowUpRight size={17}/></button></section>
    <div className="stats">{cards.map(([label, state, Icon]) => <button key={state} className="stat" onClick={() => setFilter(state)}>
      <span className={'stat-icon ' + state}><Icon size={20}/></span><span>{label}</span><strong>{posts.filter(post => post.status === state).length}</strong>
    </button>)}</div>
    <section className="panel">
      <div className="panel-head"><div><h2>Posts</h2><p className="muted">Manage drafts and scheduled content.</p></div>
        <label className="sr-only" htmlFor="filter">Filter by status</label><select id="filter" value={filter} onChange={e => setFilter(e.target.value)}>
          {filters.map(option => <option key={option} value={option}>{option === 'all' ? 'All statuses' : option[0].toUpperCase() + option.slice(1)}</option>)}
        </select></div>
      {shown.length ? <div className="table-scroll"><table><thead><tr><th>Post</th><th>Platform</th><th>Schedule</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>{shown.map(post => <tr key={post.id}><td><strong className="post-title">{post.caption || post.hashtags || 'Untitled post'}</strong>
          {post.failure && <small className="failure">{post.failure}</small>}
          {post.ai_assisted && <small className="muted">AI-assisted</small>}</td>
          <td><Platform name={post.platform}/></td><td>{dateLabel(post.scheduled_at)}</td>
          <td><span className={'badge ' + post.status}>{post.status}</span></td>
          <td className="actions">{!['published', 'publishing'].includes(post.status) && <button className="text-button" onClick={() => edit(post)}>{post.status === 'failed' ? 'Reschedule' : 'Edit'}</button>}
            {post.status === 'scheduled' && <button className="text-button danger" onClick={() => cancel(post.id)}>Cancel</button>}
            {post.published_at && <small>Published {dateLabel(post.published_at)}</small>}</td></tr>)}</tbody>
      </table></div> : <div className="empty"><FileText size={28}/><strong>{filter === 'all' ? 'No posts yet' : 'No ' + filter + ' posts'}</strong>
        {filter === 'all' && <button className="text-button" onClick={create}>Create your first post</button>}</div>}
    </section>
  </>;
}

function Composer({post, accounts, onSaved, openAccounts}) {
  const [form, setForm] = useState({...fresh, ...post, account: post?.account || '', scheduled_at: toLocal(post?.scheduled_at)});
  const [topic, setTopic] = useState('');
  const [action, setAction] = useState('caption');
  const [suggestion, setSuggestion] = useState(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [aiError, setAiError] = useState('');
  const set = (key, value) => setForm(current => ({...current, [key]: value}));
  const matches = accounts.filter(account => account.platform === form.platform);

  async function save(event) {
    event.preventDefault();
    const scheduling = event.nativeEvent.submitter?.value === 'schedule';
    if (scheduling && !form.scheduled_at) return setError('Choose a date and time first.');
    setSaving(true);
    setError('');
    try {
      const data = form.media_file ? new FormData() : {...form, generated_media_path: form.media_path, account: form.account || null, scheduled_at: scheduling ? new Date(form.scheduled_at).toISOString() : null};
      if (data instanceof FormData) {
        Object.entries({...form, generated_media_path: form.media_path, account: form.account || '', scheduled_at: scheduling ? new Date(form.scheduled_at).toISOString() : ''})
          .filter(([key, value]) => !['media_file', 'media_path'].includes(key) && value !== null && value !== undefined)
          .forEach(([key, value]) => data.append(key, value));
        data.append('media_file', form.media_file);
      }
      await api(post ? 'posts/' + post.id : 'posts', post ? 'PUT' : 'POST', data);
      onSaved(scheduling ? 'Post scheduled' : 'Draft saved');
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function generate(event) {
    event.preventDefault();
    setGenerating(true);
    setSuggestion(null);
    setAiError('');
    try {
      const input = action === 'refine' ? form.caption : topic;
      if (action === 'image') {
        const generated = await api('generate-image', 'POST', {prompt: input});
        setSuggestion({text: input, image_url: generated.media_url, media_path: generated.media_path, source: generated.source, action});
      } else {
        setSuggestion({...await api('assistant', 'POST', {action, topic: input, platform: form.platform}), action});
      }
    } catch (err) {
      setAiError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  function apply() {
    if (suggestion.action === 'image') {
      setForm(current => ({...current, media_url: suggestion.image_url, media_path: suggestion.media_path, media_file: null}));
      setSuggestion(null);
      return;
    }
    const field = suggestion.action === 'hashtags' ? 'hashtags' : 'caption';
    setForm(current => ({...current, [field]: suggestion.text, ai_assisted: true}));
    setSuggestion(null);
  }

  return <>
    <header className="page-heading"><div><h1>{post ? 'Edit post' : 'New post'}</h1><p>Write your post, then save it for later or pick a publishing time.</p></div></header>
    <div className="editor-grid">
      <form className="panel padded form-grid" onSubmit={save}>
        <h2>Post details</h2>
        <div className="columns">
          <label>Platform<select value={form.platform} onChange={e => {setForm(current => ({...current, platform: e.target.value, account: ''})); setSuggestion(null);}}>
            {Object.entries(platforms).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select></label>
          <label>Account<select value={form.account} onChange={e => set('account', e.target.value)}>
            <option value="">Choose an account</option>{matches.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select></label>
        </div>
        {!matches.length && <button className="text-button left" type="button" onClick={openAccounts}>Connect an account</button>}
        <label>Caption<textarea rows="6" value={form.caption} maxLength="5000" onChange={e => set('caption', e.target.value)} placeholder="What would you like to share?"/></label>
        <label>Hashtags<input value={form.hashtags} maxLength="500" onChange={e => set('hashtags', e.target.value)} placeholder="#YourTopic"/></label>
        <label>Image URL<input type="url" value={form.media_url} maxLength="1000" onChange={e => setForm(current => ({...current, media_url: e.target.value, media_path: ''}))} placeholder="https://example.com/photo.jpg"/>
          <small>{form.platform === 'instagram' ? 'Use a public URL or upload a JPEG below.' : 'Optional. Use a public HTTPS image URL.'}</small></label>
        <label>Or upload image<input type="file" accept="image/jpeg,image/png" onChange={e => setForm(current => ({...current, media_file: e.target.files?.[0] || null, media_path: '', media_url: ''}))}/>
          <small>{form.media_file ? form.media_file.name : 'Stored by Django in the local media folder.'}</small></label>
        <label>Publish date and time<input type="datetime-local" value={form.scheduled_at} onChange={e => set('scheduled_at', e.target.value)}/>
          <small>{Intl.DateTimeFormat().resolvedOptions().timeZone}</small></label>
        <ErrorText message={error}/>
        <div className="button-row">
          <button className="secondary" value="draft" disabled={saving}>Save draft</button>
          <button className="primary" value="schedule" disabled={saving}><CalendarDays size={17}/> Schedule post</button>
        </div>
      </form>
      <aside className="panel padded assistant">
        <div className="assistant-heading"><span><Sparkles size={20}/></span><h2>AI assistant</h2></div>
        <form onSubmit={generate} className="form-grid">
          <label>Task<select value={action} onChange={e => {setAction(e.target.value); setSuggestion(null);}}>
            <option value="caption">Generate caption</option><option value="refine">Improve caption</option>
            <option value="hashtags">Suggest hashtags</option><option value="ideas">Brainstorm ideas</option>
            <option value="image">Generate image</option>
          </select></label>
          {action === 'refine' ? <p className="muted">The assistant will use the caption in your draft.</p> :
            <label>Topic<textarea rows="3" value={topic} maxLength="5000" required onChange={e => setTopic(e.target.value)} placeholder="Describe your post or campaign"/></label>}
          <button className="primary" disabled={generating || (action === 'refine' && !form.caption.trim())}><Sparkles size={16}/>{generating ? 'Generating…' : 'Generate suggestion'}</button>
          <ErrorText message={aiError}/>
        </form>
        {suggestion && <div className="suggestion"><strong>{suggestion.source === 'demo' ? 'Demo suggestion' : 'Gemini suggestion'}</strong>
          {suggestion.image_url && <img className="generated-image" src={suggestion.image_url} alt="Generated preview"/>}
          <p>{suggestion.text}</p>
          <button className="secondary" onClick={apply}>{suggestion.action === 'image' ? 'Use image' : suggestion.action === 'hashtags' ? 'Use hashtags' : 'Use as caption'}</button></div>}
      </aside>
    </div>
  </>;
}

function Accounts({accounts, demo, onConnected}) {
  const [platform, setPlatform] = useState('facebook');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  async function connect(data, form) {
    setPending(true);
    setError('');
    try {
      await api('accounts', 'POST', {platform, ...data});
      form?.reset();
      onConnected();
    } catch (err) {
      setError(err.message);
    } finally {
      setPending(false);
    }
  }

  return <>
    <header className="page-heading"><div><h1>Accounts</h1><p>Connect the Facebook Pages and Instagram profiles you publish to.</p></div></header>
    <div className="editor-grid">
      <section className="panel padded"><h2>Connected accounts</h2>
        {accounts.length ? <ul className="account-list">{accounts.map(account => <li key={account.id}>
          <div><strong>{account.name}</strong><Platform name={account.platform}/></div>
          <span className={'badge ' + (account.demo ? 'draft' : 'published')}>{account.demo ? 'Demo' : 'Connected'}</span>
        </li>)}</ul> : <div className="empty"><Link2 size={28}/><strong>No accounts connected</strong></div>}
      </section>
      <form className="panel padded form-grid" onSubmit={event => {
        event.preventDefault();
        connect(Object.fromEntries(new FormData(event.currentTarget)), event.currentTarget);
      }}>
        <h2>Connect an account</h2>
        <label>Platform<select value={platform} onChange={e => setPlatform(e.target.value)}>
          {Object.entries(platforms).map(([id, name]) => <option key={id} value={id}>{name}</option>)}
        </select></label>
        <label>{platform === 'facebook' ? 'Page ID' : 'Instagram professional account ID'}<input name="external_id" inputMode="numeric" pattern="[0-9]+" required/></label>
        <label>Facebook Page access token<input name="token" type="password" autoComplete="off" required/>
          {platform === 'instagram' && <small>Use the token from the Facebook Page linked to this profile.</small>}</label>
        <ErrorText message={error}/>
        <button className="primary" disabled={pending}>Connect Meta account</button>
        {demo && <button className="secondary" type="button" disabled={pending} onClick={() => connect({demo: true})}>Add demo {platforms[platform]} account</button>}
      </form>
    </div>
  </>;
}

function Workspace({session, onSignOut}) {
  const [view, setView] = useState('Overview');
  const [post, setPost] = useState(null);
  const [editorVersion, setEditorVersion] = useState(0);
  const [posts, setPosts] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [returnToComposer, setReturnToComposer] = useState(false);

  async function load() {
    try {
      const [nextPosts, nextAccounts] = await Promise.all([api('posts'), api('accounts')]);
      setPosts(nextPosts);
      setAccounts(nextAccounts);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 12000);
    return () => clearInterval(timer);
  }, []);

  function edit(value) {
    setPost(value);
    setEditorVersion(v => v + 1);
    setView('Composer');
    setNotice('');
  }

  async function cancel(id) {
    if (!window.confirm('Cancel this scheduled post?')) return;
    try {
      await api('posts/' + id + '/cancel', 'POST');
      await load();
      setNotice('Post cancelled');
    } catch (err) {
      setError(err.message);
    }
  }

  async function signOut() {
    try {
      await api('logout', 'POST');
      onSignOut();
    } catch (err) {
      setError(err.message);
    }
  }

  return <div className="workspace">
    <aside className="sidebar"><Brand/><nav aria-label="Workspace">
      {views.map(({label, icon: Icon}) => <button key={label} aria-current={view === label ? 'page' : undefined}
        onClick={() => {if (label === 'Composer' && view !== 'Composer') {edit(null);} setView(label); setReturnToComposer(false); setNotice('');}}><Icon size={19}/>{label}</button>)}
    </nav><div className="sidebar-bottom"><div className="identity"><span>{session.user.username[0].toUpperCase()}</span><strong>{session.user.username}</strong></div>
      <button onClick={signOut}><LogOut size={18}/> Sign out</button></div></aside>
    <main className="main">
      <div className="top"><span>Workspace <ChevronDown size={14}/> {view}</span>{session.demo && <span className="badge draft">Demo enabled</span>}</div>
      <div className="content">
        <ErrorText message={error}/>{notice && <p className="notice" role="status"><Check size={17}/>{notice}</p>}
        {loading ? <p className="muted" role="status">Loading workspace…</p> : <>
          {view === 'Overview' && <Dashboard posts={posts} edit={edit} create={() => edit(null)} cancel={cancel}/>}
          <div hidden={view !== 'Composer'}><Composer key={editorVersion} post={post} accounts={accounts}
            openAccounts={() => {setReturnToComposer(true); setView('Accounts');}}
            onSaved={message => {setView('Overview'); setNotice(message); load();}}/></div>
          {view === 'Accounts' && <Accounts accounts={accounts} demo={session.demo} onConnected={async () => {
            await load();
            setNotice('Account connected');
            if (returnToComposer) {setView('Composer'); setReturnToComposer(false);}
          }}/>}
        </>}
      </div>
    </main>
  </div>;
}

function App() {
  const [session, setSession] = useState(null);
  const [error, setError] = useState('');
  useEffect(() => {api('session').then(setSession).catch(err => setError(err.message));}, []);
  if (!session) return <main className="loading">{error ? <ErrorText message={error}/> : 'Loading Postline…'}</main>;
  const changeUser = user => setSession(current => ({...current, user}));
  return session.user ? <Workspace session={session} onSignOut={() => changeUser(null)}/> : <SignIn onSignedIn={changeUser}/>;
}

createRoot(document.getElementById('root')).render(<App/>);

