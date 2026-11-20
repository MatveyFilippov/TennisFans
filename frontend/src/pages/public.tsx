import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { params, photoUrl, request, useData, type Match, type Model, type Page, type PublicUser } from '../api'
import { dateTime, rankRange, useI18n } from '../i18n'
import { Gallery } from '../components/media'
import { Avatar, Badge, Chart, Data, DateMarker, Empty, Heading, historySeries, MatchList, Pager, Panel, PlayerLink, PlayerPicker } from '../components/ui'
import courtPhoto from '../assets/court.webp'

export function HomePage() {
  const { t } = useI18n()
  const matches = useData<Page<Match>>('/public/matches?limit=4')
  const tournaments = useQuery({
    queryKey: ['/public/tournaments?status=SCHEDULED', 'upcoming'],
    queryFn: async () => {
      const items: Model['TournamentSummary'][] = []
      let total = Infinity
      while (items.length < total) {
        const page = await request<Page<Model['TournamentSummary']>>(`/public/tournaments?status=SCHEDULED&limit=100&offset=${items.length}`)
        if (!page.items.length) break
        items.push(...page.items)
        total = page.total
      }
      return items.sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)).slice(0, 4)
    },
  })
  const ratings = useData<Page<Model['Leader']>>('/public/ratings?limit=3')
  return <>
    <section className="hero">
      <img className="hero-photo" src={courtPhoto} alt="" fetchPriority="high" />
      <div className="hero-inner">
        <p className="eyebrow">{t('amateurTennis')}</p>
        <h1>{t('brand')}</h1><h2>{t('slogan')}</h2><p>{t('intro')}</p>
        <div className="actions"><Link className="button primary" to="/friendlies/new">{t('recordMatch')} <span aria-hidden="true">↗</span></Link>
          <Link className="button hero-secondary" to="/tournaments">{t('browseTournaments')} <span aria-hidden="true">↗</span></Link></div>
      </div>
    </section>
    <div className="club-feed">
      <h2 className="feed-heading">{t('onCourt')}</h2>
      <Panel title={t('upcoming')} action={<Link to="/tournaments">{t('viewAll')} <span aria-hidden="true">↗</span></Link>}>
        <Data query={tournaments}>{data => <TournamentCards items={data} />}</Data>
      </Panel>
      <Panel title={t('recent')} action={<Link to="/matches">{t('viewAll')}</Link>}>
        <Data query={matches}>{data => <MatchList items={data.items} />}</Data>
      </Panel>
      <Panel title={t('topPlayers')} action={<Link to="/ratings">{t('viewAll')}</Link>}>
        <Data query={ratings}>{data => data.items.length ? <ol className="leader-strip">{data.items.map(row => <li key={row.id}>
          <span className="muted">{row.rank}.</span><PlayerLink user={row} /><strong>{Math.round(row.rating)}</strong>
        </li>)}</ol> : <Empty />}</Data>
      </Panel>
    </div>
  </>
}

export function TournamentCards({ items }: { items: Model['TournamentSummary'][] }) {
  const { t, language } = useI18n()
  if (!items.length) return <Empty message={t('tournamentEmpty')} />
  return <ul className="tour-list">{items.map(item => <li key={item.id}>
    <DateMarker value={item.starts_at} timeZone={item.timezone} />
    <div className="tour-body">
      {item.cover_id && <Link to={`/tournaments/${item.id}`} className="tour-thumb" tabIndex={-1} aria-hidden="true"><img src={photoUrl(item.cover_id)} alt="" loading="lazy" crossOrigin="anonymous" /></Link>}
      <div className="tour-info"><Link className="tour-title" to={`/tournaments/${item.id}`}>{item.title} <span aria-hidden="true">↗</span></Link>
      <p className="muted"><time dateTime={item.starts_at}>{dateTime(language, item.starts_at, item.timezone)}</time></p>
      <div className="meta"><Badge value={item.status} /><span>{t(item.discipline)}</span>
        {item.applications_open && <span>{t('openApplications')}</span>}
        <span aria-label={t('accepted')}>{item.accepted}/{item.capacity}</span>
      </div>
      </div>
    </div>
  </li>)}</ul>
}

export function TournamentIndex({ admin }: { admin: boolean }) {
  const { t } = useI18n()
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const query = useData<Page<Model['TournamentSummary']>>('/public/tournaments' + params({ q: search, status, offset }))
  return <>
    <Heading title={t('tournaments')} subtitle={t('tournamentIntro')} action={admin && <Link className="button primary" to="/tournaments/new">{t('newTournament')}</Link>} />
    <div className="toolbar">
      <label>{t('search')}<input type="search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0) }} /></label>
      <label>{t('filterStatus')}<select value={status} onChange={e => { setStatus(e.target.value); setOffset(0) }}>
        {['', 'SCHEDULED', 'ACTION_REQUIRED', 'ACTIVE', 'COMPLETED'].map(key => <option value={key} key={key}>{t(key || 'all')}</option>)}</select></label>
    </div>
    <Data query={query}>{data => <><TournamentCards items={data.items} /><Pager offset={offset} total={data.total} onChange={setOffset} /></>}</Data>
  </>
}

function Ranking({ rows, compact = false }: { rows: Model['Leader'][], compact?: boolean }) {
  const { t, language } = useI18n()
  const number = new Intl.NumberFormat(language)
  if (!rows.length) return <Empty />
  return <div className="table-wrap ranking-wrap" tabIndex={0} aria-label={t('ratings')} role="region"><table className={compact ? 'compact-ranking' : 'ranking'}>
    <thead><tr>{(compact ? ['rank', 'PLAYER', 'elo'] : ['rank', 'PLAYER', 'elo', 'matches', 'wins', 'losses', 'winRate', 'trend'])
      .map(key => <th scope="col" key={key}>{t(key)}</th>)}</tr></thead>
    <tbody>{rows.map(row => <tr key={row.id}>
      <td>{number.format(row.rank)}</td><th scope="row"><PlayerLink user={row} avatar /></th><td><strong>{number.format(Math.round(row.rating))}</strong></td>
      {!compact && <><td>{number.format(row.matches)}</td><td>{number.format(row.wins)}</td><td>{number.format(row.losses)}</td>
        <td>{new Intl.NumberFormat(language, { style: 'percent', maximumFractionDigits: 1 }).format(row.win_rate)}</td>
        <td><Chart compact series={[{ name: row.display_name, points: row.trend.map((y, x) => ({ x, y })) }]} /></td></>}
    </tr>)}</tbody>
  </table></div>
}

export function Directory({ ratings = false }: { ratings?: boolean }) {
  const { t } = useI18n()
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const query = useData<Page<PublicUser>>('/public/users' + params({ q: search, offset }), !ratings)
  const leaders = useData<Page<Model['Leader']>>('/public/ratings' + params({ q: search, offset }), ratings)
  return <>
    <Heading title={t(ratings ? 'ratings' : 'players')} subtitle={t(ratings ? 'ratingIntro' : 'playerIntro')} action={<Link className="button" to="/compare">{t('compare')}</Link>} />
    <div className="toolbar"><label>{t('search')}<input type="search" value={search} onChange={e => { setSearch(e.target.value); setOffset(0) }} /></label></div>
    {ratings
      ? <Data query={leaders}>{data => <><Ranking rows={data.items} /><Pager offset={offset} total={data.total} onChange={setOffset} /></>}</Data>
      : <Data query={query}>{data => <>{data.items.length ? <ul className="player-directory">{data.items.map(user => <li key={user.id}>
        <PlayerLink user={user} avatar /><span className="muted">@{user.username}</span>
        <strong>{Math.round(user.rating)} <small>{t('elo')}</small></strong>
      </li>)}</ul> : <Empty message={t('playerEmpty')} />}<Pager offset={offset} total={data.total} onChange={setOffset} /></>}</Data>}
  </>
}

function Totals({ title, item }: { title: string, item: Model['Totals'] }) {
  const { t, language } = useI18n()
  const n = new Intl.NumberFormat(language)
  const pairs = {
    matches: item.matches ?? 0, wins: item.wins ?? 0, losses: item.losses ?? 0,
    winRate: new Intl.NumberFormat(language, { style: 'percent', maximumFractionDigits: 1 }).format(item.win_rate ?? 0),
    sets: `${item.sets_won ?? 0}–${item.sets_lost ?? 0} (${(item.sets_won ?? 0) - (item.sets_lost ?? 0)})`,
    games: `${item.games_won ?? 0}–${item.games_lost ?? 0} (${(item.games_won ?? 0) - (item.games_lost ?? 0)})`,
    currentStreak: item.current_streak ?? 0, longestStreak: item.longest_streak ?? 0,
  }
  return <Panel title={title}><dl className="metrics">{Object.entries(pairs).map(([label, value]) => <div key={label}>
    <dt>{t(label)}</dt><dd>{typeof value === 'number' ? n.format(value) : value}</dd>
  </div>)}</dl></Panel>
}

export function PlayerPage() {
  const { id } = useParams()
  const { t, language } = useI18n()
  const query = useData<Model['PlayerStats']>(`/public/users/${id}`)
  return <Data query={query}>{data => <>
    <div className="profile-heading"><Avatar user={data.player} />
      <Heading title={data.player.display_name} subtitle={`@${data.player.username}`}
        action={<span className="rank-number">{Math.round(data.player.rating)} <small>{t('elo')}</small></span>} />
    </div>
    {!data.player.active && <Badge value="inactive" />}
    <div className="stack">
      <Panel title={t('eloHistory')}><Chart series={[historySeries(data.player, data.history)]} />
        {!!data.history.length && <details><summary>{t('details')}</summary><ul className="clean-list">
          {[...data.history].reverse().map(item => <li key={item.match_id}><Link to={`/matches/${item.match_id}`}>
            {dateTime(language, item.played_at)} · {Math.round(item.rating_after)} {t('elo')}
          </Link></li>)}
        </ul></details>}
      </Panel>
      <div className="totals-grid"><Totals title={t('overall')} item={data.overall} />
        <Totals title={t('SINGLES')} item={data.singles} /><Totals title={t('DOUBLES')} item={data.doubles} /></div>
      <Panel title={t('recent')} action={<Link to={`/matches?player=${id}`}>{t('viewAll')}</Link>}><MatchList items={data.recent} /></Panel>
      {!!data.gallery.length && <Gallery photos={data.gallery} />}
      <Panel title={t('tournaments')}>
        {data.tournaments.length ? <ul className="clean-list">{data.tournaments.map(item => <li key={item.tournament.id}>
          <Link to={`/tournaments/${item.tournament.id}`}>{item.tournament.title}</Link>
          {item.rank != null && <> · {t('rank')} {rankRange(item.rank, item.rank_end ?? item.rank)}</>}
        </li>)}</ul> : <Empty />}
      </Panel>
    </div>
  </>}</Data>
}

export function ComparePage() {
  const [a, setA] = useState<PublicUser | null>(null)
  const [b, setB] = useState<PublicUser | null>(null)
  const { t } = useI18n()
  const query = useData<Model['PairStats']>(`/public/stats/compare/${a?.id}/${b?.id}`, !!a && !!b)
  return <>
    <Heading title={t('compare')} subtitle={t('compareIntro')} />
    <div className="form-grid">
      <PlayerPicker label={t('sideA')} value={a} onChange={setA} exclude={b ? [b.id] : []} />
      <PlayerPicker label={t('sideB')} value={b} onChange={setB} exclude={a ? [a.id] : []} />
    </div>
    {a && b && <Data query={query}>{data => <div className="stack">
      <Panel title={t('eloHistory')}><Chart series={[historySeries(a, data.a.history), historySeries(b, data.b.history)]} />
        <div className="form-grid"><PlayerLink user={a} avatar /><PlayerLink user={b} avatar />
          <strong>{Math.round(a.rating)} {t('elo')}</strong><strong>{Math.round(b.rating)} {t('elo')}</strong></div></Panel>
      <div className="form-grid"><Totals title={a.display_name} item={data.a.overall} /><Totals title={b.display_name} item={data.b.overall} /></div>
      <Panel title={t('headToHead')}><p>{data.a_wins}–{data.b_wins} · {data.opponent_total} {t('matches')}</p><MatchList items={data.opponent_matches} /></Panel>
      <Panel title={t('partners')}><p>{t('togetherWins')} {data.partner_wins}/{data.partner_total}</p><MatchList items={data.partner_matches} /></Panel>
    </div>}</Data>}
  </>
}
