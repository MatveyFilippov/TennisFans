import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { params, useAction, useData, type Account, type Model, type Page } from '../api'
import { Upload } from '../components/media'
import { Alert, Avatar, Badge, Data, Empty, Heading, Pager, Panel } from '../components/ui'
import { dateTime, useI18n } from '../i18n'
import courtPhoto from '../assets/court.webp'

export function LoginPage({ create = false }: { create?: boolean }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const mutation = useAction<Account>()
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const name = fields.get('display_name')
    mutation.mutate({
      path: create ? '/auth/register' : '/auth/login', body: {
        username: fields.get('username'), password: fields.get('password'),
        ...(create && name && { display_name: name }),
      },
    }, {
      onSuccess: result => {
        const from: unknown = location.state?.from
        navigate(result.password_change_required ? '/account' : typeof from === 'string' && from.startsWith('/') && !from.startsWith('//') ? from : '/account', { replace: true })
      },
    })
  }
  return <div className="auth-layout"><div className="auth-content">
    <Heading title={t(create ? 'register' : 'signIn')} />
    <form className="card-form" onSubmit={submit}>
      <label>{t('username')}<input name="username" autoComplete="username" required pattern="[a-zA-Z0-9_\-]{3,32}" /></label>
      {create && <label>{t('displayName')}<input name="display_name" maxLength={80} autoComplete="nickname" /></label>}
      <label>{t('password')}<input name="password" type="password" required minLength={create ? 12 : 1}
        maxLength={128} autoComplete={create ? 'new-password' : 'current-password'} /></label>
      {create && <p className="muted">{t('passwordRule')}</p>}
      <Alert error={mutation.error} />
      <button className="primary" disabled={mutation.isPending}>{t(mutation.isPending ? 'saving' : create ? 'register' : 'signIn')}</button>
      <Link to={create ? '/login' : '/register'} state={location.state}>{t(create ? 'signIn' : 'register')}</Link>
    </form>
    </div><img className="auth-photo" src={courtPhoto} alt="" />
  </div>
}

function PasswordForm({ restricted }: { restricted: boolean }) {
  const { t } = useI18n()
  const mutation = useAction<Account>()
  return <form className="card-form no-frame" onSubmit={event => {
    event.preventDefault()
    const form = event.currentTarget
    const body = new FormData(form)
    mutation.mutate({ path: '/auth/password', body: {
      old_password: body.get('old_password') ?? '', new_password: body.get('new_password'),
    } }, { onSuccess: () => form.reset() })
  }}>
    {restricted ? <p role="status">{t('passwordRequired')}</p> :
      <label>{t('oldPassword')}<input required name="old_password" type="password" autoComplete="current-password" maxLength={128} /></label>}
    <label>{t('newPassword')}<input required name="new_password" type="password" autoComplete="new-password" minLength={12} maxLength={128} /></label>
    <p className="muted">{t('passwordRule')}</p>
    <Alert error={mutation.error} />
    {mutation.isSuccess && <p role="status">{t('saved')}</p>}
    <button className="primary" disabled={mutation.isPending}>{t(mutation.isPending ? 'saving' : 'changePassword')}</button>
  </form>
}

export function AccountPage({ account }: { account: Account }) {
  const { t, language } = useI18n()
  const navigate = useNavigate()
  const user = account.user
  const edit = useAction<Model['ManagedUser']>()
  const logout = useAction()
  const [offset, setOffset] = useState(0)
  const notifications = useData<Page<Model['NotificationView']>>('/account/notifications' + params({ offset }), !account.password_change_required)
  return <>
    <Heading title={t('account')} subtitle={t('accountIntro')} action={<button onClick={() => logout.mutate({ path: '/auth/logout' }, {
      onSuccess: () => navigate('/'),
    })} disabled={logout.isPending}>{t('logout')}</button>} />
    <Alert error={logout.error} />
    <div className="account-layout">
      <nav className="section-nav" aria-label={t('account')}>
        {!account.password_change_required && <><a href="#profile">{t('profile')}</a><a href="#notifications">{t('notifications')}</a></>}
        <a href="#password">{t('changePassword')}</a>
      </nav>
      <div className="stack">
      {!account.password_change_required && <>
        <section id="profile"><Panel title={t('profile')} action={<Link to={`/players/${user.id}`}>{t('viewProfile')}</Link>}>
          <Avatar user={user} />
          <form className="card-form no-frame" onSubmit={event => {
            event.preventDefault()
            const data = new FormData(event.currentTarget)
            edit.mutate({ path: '/account', method: 'PATCH', body: { display_name: data.get('display_name') } })
          }}>
            <label>{t('displayName')}<input name="display_name" required maxLength={80} defaultValue={user.display_name} /></label>
            <Alert error={edit.error} />
            {edit.isSuccess && <p role="status">{t('saved')}</p>}
            <button className="primary" disabled={edit.isPending}>{t('save')}</button>
          </form>
          <Upload kind="user" owner={user.id} multiple={false} />
        </Panel></section>
        <section id="notifications"><Panel title={t('notifications')}>
          <Data query={notifications}>{data => <>
            {data.items.length ? <ul className="clean-list">{data.items.map(item => <li key={item.id}>
              <time>{dateTime(language, item.created_at)}</time>
              <p>{t('notification')} <Badge value={item.decision} /></p>
              {item.match_id && <Link to={`/matches/${item.match_id}`}>{t('details')}</Link>}
            </li>)}</ul> : <Empty />}
            <Pager offset={offset} total={data.total} onChange={setOffset} />
          </>}</Data>
        </Panel></section>
      </>}
      <section id="password"><Panel title={t('changePassword')}><PasswordForm restricted={account.password_change_required} /></Panel></section>
      </div>
    </div>
  </>
}

function AdminUser({ user }: { user: Model['ManagedUser'] }) {
  const { t, language } = useI18n()
  const [confirm, setConfirm] = useState(false)
  const mutation = useAction<Model['ManagedUser']>()
  const reset = useAction<Model['Reset']>()
  return <details className="admin-user"><summary><Avatar user={user} /> {user.display_name} · @{user.username} · {t(user.role)}</summary>
    <form className="card-form no-frame" onSubmit={event => {
      event.preventDefault()
      const fields = new FormData(event.currentTarget)
      mutation.mutate({ path: `/admin/users/${user.id}`, method: 'PATCH', body: {
        display_name: fields.get('display_name'), username: fields.get('username'), role: fields.get('role'), active: fields.has('active'),
      } })
    }}>
      <div className="form-grid">
        <label>{t('displayName')}<input name="display_name" required maxLength={80} defaultValue={user.display_name} /></label>
        <label>{t('username')}<input name="username" required pattern="[a-zA-Z0-9_\-]{3,32}" defaultValue={user.username} /></label>
        <label>{t('role')}<select name="role" defaultValue={user.role}>
          {['PLAYER', 'ADMIN'].map(item => <option key={item} value={item}>{t(item)}</option>)}</select></label>
        <label className="check"><input type="checkbox" name="active" defaultChecked={user.active} />{t('activeAccount')}</label>
      </div>
      <Alert error={mutation.error} />
      {mutation.isSuccess && <p role="status">{t('saved')}</p>}
      <button className="primary" disabled={mutation.isPending}>{t('save')}</button>
    </form>
    <Upload kind="user" owner={user.id} multiple={false} />
    <div className="actions">{confirm ? <>
      <button className="danger" disabled={reset.isPending} onClick={() => reset.mutate({ path: `/admin/users/${user.id}/reset` },
        { onSuccess: () => setConfirm(false) })}>{t('confirm')}</button>
      <button onClick={() => setConfirm(false)}>{t('cancel')}</button>
    </> : <button onClick={() => { reset.reset(); setConfirm(true) }}>{t('resetPassword')}</button>}</div>
    <Alert error={reset.error} />
    {reset.data && <div className="notice" role="status">
      <label>{t('tempPassword')}<input readOnly value={reset.data.temporary_password} onFocus={e => e.currentTarget.select()} autoComplete="off" /></label>
      <p>{t('expires')} {dateTime(language, reset.data.expires_at)}</p>
      <button onClick={() => reset.reset()}>{t('dismiss')}</button>
    </div>}
  </details>
}

export function AdminPage() {
  const { t } = useI18n()
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const users = useData<Page<Model['ManagedUser']>>('/admin/users' + params({ q: search, offset }))
  const action = useAction()
  const [confirm, setConfirm] = useState(false)
  return <>
    <Heading title={t('adminTitle')} subtitle={t('adminIntro')} action={<Link className="button" to="/admin/audit">{t('audit')}</Link>} />
    <div className="actions">
      {confirm ? <>
        <button className="primary" disabled={action.isPending} onClick={() => action.mutate({ path: '/admin/ratings/rebuild' },
          { onSuccess: () => setConfirm(false) })}>{t('confirm')}</button>
        <button onClick={() => setConfirm(false)}>{t('cancel')}</button>
      </> : <button onClick={() => setConfirm(true)}>{t('rebuild')}</button>}
      {action.isSuccess && <p role="status">{t('saved')}</p>}
      <Alert error={action.error} />
    </div>
    <div className="toolbar"><label>{t('search')}<input type="search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0) }} /></label></div>
    <Data query={users}>{data => <>
      {data.items.length ? data.items.map(user => <AdminUser user={user} key={user.id} />) : <Empty />}
      <Pager offset={offset} total={data.total} onChange={setOffset} />
    </>}</Data>
  </>
}

export function AuditPage() {
  const { t, language } = useI18n()
  const [filter, setFilter] = useState('')
  const [offset, setOffset] = useState(0)
  const query = useData<Page<Model['AuditView']>>('/admin/audit' + params({ action: filter, offset }))
  return <>
    <Heading title={t('audit')} subtitle={t('auditIntro')} />
    <div className="toolbar"><label>{t('action')}<input value={filter} onChange={event => { setFilter(event.target.value); setOffset(0) }} /></label></div>
    <Data query={query}>{data => <>
      {data.items.length ? <ul className="clean-list">{data.items.map(item => <li key={item.id} className="audit-row">
        <time>{dateTime(language, item.created_at)}</time> <Badge value={item.action} />
        {item.actor_id && <Link to={`/players/${item.actor_id}`}>{t('actor')} {item.actor_id.slice(0, 8)}</Link>}
        <details><summary>{t('details')}</summary><p>{item.target_id}</p><pre>{JSON.stringify(item.details, null, 2)}</pre></details>
      </li>)}</ul> : <Empty />}
      <Pager offset={offset} total={data.total} onChange={setOffset} />
    </>}</Data>
  </>
}
