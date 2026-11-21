import { useId, useState, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { errorKey, params, photoUrl, useData, type Match, type Model, type Page, type PublicUser } from '../api'
import { dateTime, useI18n } from '../i18n'

export function Heading({ title, subtitle, action }: { title: string, subtitle?: string, action?: ReactNode }) {
  const { t } = useI18n()
  const { pathname } = useLocation()
  const parent = pathname.startsWith('/matches/') || pathname === '/friendlies/new' ? ['matches', '/matches']
    : pathname.startsWith('/tournaments/') ? ['tournaments', '/tournaments']
    : pathname.startsWith('/players/') ? ['players', '/players']
    : pathname === '/admin/audit' ? ['admin', '/admin'] : undefined
  return <header className="page-heading">
    {parent && <Link className="back-link" to={parent[1]}><span aria-hidden="true">←</span> {t(parent[0])}</Link>}
    <div className="heading-content"><div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
  </header>
}

export function Panel({ title, action, children }: { title: string, action?: ReactNode, children: ReactNode }) {
  return <section className="panel"><header className="section-heading"><h2>{title}</h2>{action}</header>{children}</section>
}

export function Alert({ error }: { error: unknown }) {
  const { t } = useI18n()
  return error ? <p className="alert" role="alert">{t(errorKey(error))}</p> : null
}

export function Empty({ message }: { message?: string }) {
  const { t } = useI18n()
  return <p className="empty">{message ?? t('empty')}</p>
}

export function Loading() {
  const { t } = useI18n()
  return <p className="empty skeleton" role="status">{t('loading')}</p>
}

export function Data<T>({ query, children }: {
  query: { data: T | undefined, error: unknown, isPending: boolean, refetch: () => unknown },
  children: (data: T) => ReactNode,
}) {
  const { t } = useI18n()
  if (query.data !== undefined) return children(query.data)
  if (query.error) return <div><Alert error={query.error} /><button onClick={() => void query.refetch()}>{t('retry')}</button></div>
  return <Loading />
}

export function Badge({ value }: { value: string }) {
  const { t } = useI18n()
  return <span className={`badge badge-${value.toLowerCase()}`}>{t(value)}</span>
}

export function Avatar({ user }: { user: PublicUser }) {
  const [failed, setFailed] = useState<string | null>(null)
  const first = [...new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(user.display_name.trim())][0]?.segment
  return <span className="avatar" aria-hidden="true">
    {user.avatar_id && user.avatar_id !== failed
      ? <img src={photoUrl(user.avatar_id)} alt="" loading="lazy" crossOrigin="anonymous" onError={() => setFailed(user.avatar_id ?? null)} />
      : first?.toUpperCase() || '–'}
  </span>
}

export function PlayerLink({ user, avatar = false }: { user: PublicUser, avatar?: boolean }) {
  return <Link className="player-link" to={`/players/${user.id}`}>
    {avatar && <Avatar user={user} />}<span>{user.display_name}</span>
  </Link>
}

export function PlayerPicker({ label, value, onChange, exclude = [] }: {
  label: string, value: PublicUser | null, onChange: (user: PublicUser | null) => void, exclude?: string[],
}) {
  const { t } = useI18n()
  const [search, setSearch] = useState('')
  const id = useId()
  const query = useData<Page<PublicUser>>('/public/users' + params({ q: search, limit: 8 }), !value)
  const available = query.data?.items.filter(user => !exclude.includes(user.id))
  return <div className="picker">
    {value
      ? <div className="selected"><span>{label}: <strong>{value.display_name}</strong></span>
        <button type="button" onClick={() => { setSearch(''); onChange(null) }}>{t('changePlayer')}</button></div>
      : <>
        <label htmlFor={id}>{label}</label>
        <input id={id} type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={t('search')} autoComplete="off" />
        <Alert error={query.error} />
        {query.isLoading && <Loading />}
        {available?.length === 0 && <Empty />}
        {!!available?.length && <ul className="choices">
          {available.map(user => <li key={user.id}><button type="button" onClick={() => onChange(user)}>
            <Avatar user={user} /><span>{user.display_name} <small>@{user.username}</small></span>
          </button></li>)}
        </ul>}
      </>}
  </div>
}

export function UserList({ users }: { users: PublicUser[] }) {
  return users.length ? <ul className="clean-list user-list">{users.map(user => <li key={user.id}><PlayerLink user={user} avatar /></li>)}</ul> : <Empty />
}

export function DateMarker({ value, timeZone }: { value?: string | null, timeZone?: string }) {
  const { language } = useI18n()
  if (!value) return <span className="date-marker" aria-hidden="true">—</span>
  const date = new Date(value)
  const day = new Intl.DateTimeFormat(language, { day: '2-digit', timeZone }).format(date)
  const month = new Intl.DateTimeFormat(language, { month: 'short', timeZone }).format(date)
  return <time className="date-marker" dateTime={value}><strong>{day}</strong><span>{month}</span></time>
}

export function ScoreText({ match }: { match: Match }) {
  const { t } = useI18n()
  if (!match.score) return <span className="muted">{t('noScore')}</span>
  return <span className="score-text">{match.score.outcome !== 'COMPETITIVE' && <Badge value={match.score.outcome ?? ''} />}
    {match.score.sets?.map((set, i) => <span key={i} className="set-chip">{set.a}:{set.b}
      {set.tiebreak_a != null && <small> ({set.tiebreak_a}:{set.tiebreak_b})</small>}</span>)}
  </span>
}

export function MatchList({ items }: { items: Match[] }) {
  const { t, language } = useI18n()
  if (!items.length) return <Empty message={t('matchEmpty')} />
  return <ul className="result-list">{items.map(match => <li key={match.id}>
    <DateMarker value={match.played_at ?? match.scheduled_at} />
    <div className="result-body">
      <div className="match-players"><span className={match.score?.winner === 0 ? 'winner' : undefined}>{match.a.map(u => u.display_name).join(' / ')}</span>
        <span className={match.score?.winner === 1 ? 'winner' : undefined}>{match.b.map(u => u.display_name).join(' / ')}</span>
        <div className="meta"><span>{t(match.discipline)}</span><Badge value={match.status} /></div>
      </div>
      <div className="match-result"><ScoreText match={match} /><Link to={`/matches/${match.id}`}>{t('details')} <span aria-hidden="true">↗</span></Link></div>
      <span className="sr-only">{(match.played_at ?? match.scheduled_at) && dateTime(language, (match.played_at ?? match.scheduled_at)!)}</span>
    </div>
  </li>)}</ul>
}

export function Pager({ offset, total, onChange, limit = 30 }: {
  offset: number, total: number, onChange: (value: number) => void, limit?: number,
}) {
  const { t, language } = useI18n()
  if (total <= limit && offset === 0) return null
  return <nav aria-label={t('page')} className="pager">
    <button onClick={() => onChange(Math.max(0, offset - limit))} disabled={offset === 0}>{t('previous')}</button>
    <span>{t('page')} {new Intl.NumberFormat(language).format(Math.floor(offset / limit) + 1)}</span>
    <button onClick={() => onChange(offset + limit)} disabled={offset + limit >= total}>{t('next')}</button>
  </nav>
}

type Series = { name: string, points: { x: number, y: number }[] }
export function Chart({ series, compact = false }: { series: Series[], compact?: boolean }) {
  const { t, language } = useI18n()
  const points = series.flatMap(item => item.points)
  if (!points.length) return compact ? <span>—</span> : <Empty />
  const [xmin, xmax] = points.reduce(([min, max], p) => [Math.min(min, p.x), Math.max(max, p.x)], [Infinity, -Infinity])
  const [ymin, ymax] = points.reduce(([min, max], p) => [Math.min(min, p.y), Math.max(max, p.y)], [Infinity, -Infinity])
  const x = (value: number) => 8 + 284 * (xmax === xmin ? 0.5 : (value - xmin) / (xmax - xmin))
  const y = (value: number) => 92 - 82 * (ymax === ymin ? 0.5 : (value - ymin) / (ymax - ymin))
  const number = (value: number) => new Intl.NumberFormat(language, { maximumFractionDigits: 0 }).format(value)
  const date = (value: number) => new Intl.DateTimeFormat(language, { day: 'numeric', month: 'short', year: 'numeric' }).format(value)
  return <div className={compact ? 'sparkline' : 'chart'}>
    {!compact && <div className="chart-scale" aria-hidden="true"><span>{number(ymax)}</span><span>{number(ymin)}</span></div>}
    <div className="chart-plot">
    <svg viewBox="0 0 300 100" role="img" aria-label={`${t('eloHistory')}: ${Math.round(ymin)}–${Math.round(ymax)}`}>
      {!compact && <path className="chart-grid" d="M 8 10 H 292 M 8 51 H 292 M 8 92 H 292" />}
      {series.map((item, i) => <g key={item.name} className={i === 0 ? 'series-a' : 'series-b'}>
        <polyline points={item.points.map(p => `${x(p.x)},${y(p.y)}`).join(' ')} />
        {item.points.length === 1 && <circle cx={x(item.points[0].x)} cy={y(item.points[0].y)} r="4" />}
      </g>)}
    </svg>
    {!compact && <div className="chart-dates"><time dateTime={new Date(xmin).toISOString()}>{date(xmin)}</time>{xmax !== xmin && <time dateTime={new Date(xmax).toISOString()}>{date(xmax)}</time>}</div>}
    </div>
    {!compact && <div className="chart-legend">{series.map(item => <span key={item.name}>{item.name}{item.points.length > 0 && <> · <strong>{number(item.points.at(-1)!.y)} {t('elo')}</strong></>}</span>)}</div>}
  </div>
}

export function historySeries(user: PublicUser, history: Model['Point'][]): Series {
  return { name: user.display_name, points: history.map(p => ({ x: Date.parse(p.played_at), y: p.rating_after })) }
}
