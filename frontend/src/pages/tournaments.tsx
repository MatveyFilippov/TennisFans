import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { params, photoUrl, useAction, useData, type Account, type Model, type Page, type PublicUser, type Tour } from '../api'
import { Gallery, Upload } from '../components/media'
import { Alert, Badge, Data, Empty, Heading, MatchList, Pager, Panel, PlayerLink, PlayerPicker, UserList } from '../components/ui'
import { RulesFields, standardRules } from '../features/scoring'
import { dateTime, localInputDate, rankRange, useI18n } from '../i18n'

function Selection({ label, users, onChange }: {
  label: string, users: PublicUser[], onChange: (users: PublicUser[]) => void,
}) {
  const { t } = useI18n()
  return <fieldset><legend>{label}</legend>
    <ul className="clean-list">{users.map(user => <li className="split" key={user.id}><PlayerLink user={user} avatar />
      <button type="button" onClick={() => onChange(users.filter(item => item.id !== user.id))}>{t('REMOVE')}</button></li>)}</ul>
    <PlayerPicker label={t('choosePlayer')} value={null} onChange={user => { if (user) onChange([...users, user]) }}
      exclude={users.map(user => user.id)} />
  </fieldset>
}

export function TournamentForm({ tournament }: { tournament?: Tour }) {
  const { t } = useI18n()
  const config = tournament?.config
  const navigate = useNavigate()
  const action = useAction<Model['Ref']>()
  const [discipline, setDiscipline] = useState<Model['Discipline']>(config?.discipline ?? 'SINGLES')
  const [format, setFormat] = useState<Model['Format']>(config?.format ?? 'ROUND_ROBIN')
  const [mode, setMode] = useState<Model['TeamMode']>(config?.team_mode ?? 'FIXED_TEAMS')
  const [rules, setRules] = useState(config?.rules ?? standardRules)
  const originalDate = config ? localInputDate(new Date(config.starts_at ?? tournament.starts_at), true) : ''
  const [start, setStart] = useState(originalDate)
  const [roster, setRoster] = useState<PublicUser[]>([])
  const [organizers, setOrganizers] = useState<PublicUser[]>([])
  const rotatingEnabled = discipline === 'DOUBLES' && format === 'ROUND_ROBIN'
  const team = discipline === 'DOUBLES' ? (rotatingEnabled ? mode : 'FIXED_TEAMS') : null
  const groups = format === 'GROUPS_THEN_PLAYOFFS'
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const seed = form.get('seed')
    const body: Model['Create'] = {
      title: String(form.get('title')), description: String(form.get('description')),
      timezone: String(form.get('timezone')), discipline, format, team_mode: team, rules,
      capacity: Number(form.get('capacity')), applications_open: form.has('applications'),
      group_count: groups ? Number(form.get('groups')) : null,
      qualifiers: groups ? Number(form.get('qualifiers')) : null,
      cycles: form.has('cycles') ? Number(form.get('cycles')) : 1,
      slot_minutes: Number(form.get('slot_minutes')), seeding: form.get('seeding') as Model['Seeding'],
      ...(seed && { seed: Number(seed) }),
      ...(start && { starts_at: start === originalDate ? config?.starts_at : new Date(start).toISOString() }),
    }
    action.mutate(tournament ? {
      path: `/tournaments/${tournament.id}`, method: 'PUT', body: { ...body, version: tournament.version },
    } : { path: '/tournaments', body: {
      ...body, participants: roster.map(item => item.id), organizers: organizers.map(item => item.id),
    } }, { onSuccess: ref => navigate(`/tournaments/${tournament?.id ?? ref?.id}`) })
  }
  return <>
    <Heading title={t(tournament ? 'editTournament' : 'newTournament')} />
    <form className="card-form tournament-form" onSubmit={submit}>
      <label>{t('title')}<input name="title" required maxLength={120} defaultValue={config?.title} /></label>
      <label>{t('description')}<textarea name="description" maxLength={5000} defaultValue={config?.description} /></label>
      <div className="form-grid">
        <label>{t('date')}<input type="datetime-local" name="starts_at" step="any" value={start} onChange={e => setStart(e.target.value)} /></label>
        <label>{t('timezone')}<input name="timezone" required defaultValue={config?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone} /></label>
        <label>{t('discipline')}<select value={discipline} onChange={e => setDiscipline(e.target.value as Model['Discipline'])}>
          {['SINGLES', 'DOUBLES'].map(v => <option key={v} value={v}>{t(v)}</option>)}</select></label>
        <label>{t('format')}<select value={format} onChange={e => setFormat(e.target.value as Model['Format'])}>
          {['ROUND_ROBIN', 'SINGLE_ELIMINATION', 'GROUPS_THEN_PLAYOFFS'].map(v => <option key={v} value={v}>{t(v)}</option>)}</select></label>
        {discipline === 'DOUBLES' && <label>{t('teamMode')}<select value={team ?? 'FIXED_TEAMS'}
          onChange={e => setMode(e.target.value as Model['TeamMode'])}>
          <option value="FIXED_TEAMS">{t('FIXED_TEAMS')}</option>
          <option value="ROTATING_PARTNERS" disabled={!rotatingEnabled}>{t('ROTATING_PARTNERS')}</option>
        </select></label>}
        <label>{t('capacity')}<input name="capacity" type="number" required
          min={Math.max(discipline === 'DOUBLES' ? 4 : 2, tournament?.accepted ?? 0)} max={128} defaultValue={config?.capacity ?? 4} /></label>
        {groups && <>
          <label>{t('groupCount')}<input name="groups" type="number" required min={2} max={32} defaultValue={config?.group_count ?? 2} /></label>
          <label>{t('qualifiers')}<input name="qualifiers" type="number" required min={1} max={32} defaultValue={config?.qualifiers ?? 1} /></label>
        </>}
        <label>{t('seeding')}<select name="seeding" defaultValue={config?.seeding ?? 'SEED_ORDER'}>
          {['SEED_ORDER', 'SEEDED_DRAW'].map(v => <option key={v} value={v}>{t(v)}</option>)}</select></label>
        <label>{t('seed')}<input name="seed" type="number" min={0} max={2147483647} defaultValue={config?.seed} /></label>
        {format !== 'SINGLE_ELIMINATION' && team !== 'ROTATING_PARTNERS' &&
          <label>{t('cycles')}<input name="cycles" type="number" min={1} max={3} defaultValue={config?.cycles ?? 1} required /></label>}
        <label>{t('slotMinutes')}<input name="slot_minutes" type="number" min={0} max={1440} defaultValue={config?.slot_minutes ?? 0} required /></label>
      </div>
      <p className="muted">{t('startHint')}</p>
      {discipline === 'DOUBLES' && <p className="muted">{t('rotatingOnly')}</p>}
      <label className="check"><input type="checkbox" name="applications" defaultChecked={config?.applications_open ?? true} />{t('openApplications')}</label>
      <RulesFields value={rules} onChange={setRules} />
      {!tournament && <>
        <Selection label={t('roster')} users={roster} onChange={setRoster} />
        <Selection label={t('organizers')} users={organizers} onChange={setOrganizers} />
      </>}
      <Alert error={action.error} />
      <button className="primary" disabled={action.isPending}>{t(action.isPending ? 'saving' : 'save')}</button>
    </form>
  </>
}

function Standings({ rows }: { rows: Model['StandingView'][] }) {
  const { t } = useI18n()
  return rows.length ? <div className="table-wrap" tabIndex={0} role="region" aria-label={t('standings')}>
    <table><thead><tr>{['rank', 'PLAYER', 'matches', 'wins', 'losses', 'sets', 'games'].map(key =>
      <th scope="col" key={key}>{t(key)}</th>)}</tr></thead>
      <tbody>{rows.map(item => <tr key={item.players.map(p => p.id).join('/')}>
        <td><strong>{rankRange(item.rank, item.rank_end)}</strong></td>
        <th scope="row"><div className="team-label">{item.players.map(p => <PlayerLink key={p.id} user={p} />)}</div></th>
        <td>{item.played}</td><td>{item.wins}</td><td>{item.losses}</td>
        <td>{item.sets_won}–{item.sets_lost}</td><td>{item.games_won}–{item.games_lost}</td>
      </tr>)}</tbody>
    </table>
  </div> : <Empty />
}

function Bracket({ tournament }: { tournament: Tour }) {
  const { t, language } = useI18n()
  const [selected, setSelected] = useState('')
  const fixtures = tournament.fixtures
  const labels = [...new Set(fixtures.map(item => item.stage))]
  const stage = labels.includes(selected) ? selected : labels[0]
  const rounds = fixtures.filter(item => item.stage === stage).reduce<Record<number, Tour["fixtures"]>>((out, item) => { (out[item.round] ??= []).push(item); return out }, {})
  return <Panel title={t('schedule')}>
    {!fixtures.length && <Empty />}
    {labels.length > 1 && <div className="tabs">{labels.map(label => <button key={label} aria-pressed={stage === label}
      onClick={() => setSelected(label)}>{t(label)}</button>)}</div>}
    <div className={stage === 'PLAYOFF' ? 'bracket' : 'round-list'} role="region" aria-label={t('schedule')} tabIndex={0}>
      {Object.entries(rounds).map(([number, list]) => <section className="bracket-round" key={number}>
        <h3>{t('round')} {number}</h3>
        {list?.map(item => <article className="fixture" key={item.id} id={`fixture-${item.id}`}>
          <div className="meta"><span>{t('round')} {number} · {item.position}</span>
            {item.group_id && <span>{t('group')} {tournament.groups.find(group => group.id === item.group_id)?.position}</span>}
            <time>{dateTime(language, item.scheduled_at, tournament.timezone)}</time>
          </div>
          {item.match ? <MatchList items={[item.match]} /> : <>
            <p>{t('waiting')}</p>
            <div className="team-label">{[...item.side_a, ...item.side_b].map(player => <PlayerLink key={player.id} user={player} />)}</div>
          </>}
          {[item.predecessor_a_id, item.predecessor_b_id].map((id, index) => {
            const prior = fixtures.find(fixture => fixture.id === id)
            return prior ? <a key={index} href={`#fixture-${prior.id}`}>{t('fromFixture')} {prior.round}.{prior.position}</a> : null
          })}
        </article>)}
      </section>)}
    </div>
  </Panel>
}

function Signup({ tournament }: { tournament: Tour }) {
  const { t } = useI18n()
  const path = `/tournaments/${tournament.id}/application`
  const status = useData<Model['ApplicationState']>(path)
  const mutation = useAction()
  return <div className="actions">
    {status.data?.status && <Badge value={status.data.status} />}
    {status.data?.status === 'PENDING'
      ? <button disabled={mutation.isPending} onClick={() => mutation.mutate({ path, method: 'DELETE' })}>{t('withdraw')}</button>
      : tournament.applications_open && (!status.data?.status || status.data.status === 'WITHDRAWN') &&
        <button className="primary" disabled={mutation.isPending || status.isPending} onClick={() => mutation.mutate({ path })}>{t('apply')}</button>}
    <Alert error={mutation.error ?? status.error} />
  </div>
}

function TeamsForm({ tournament }: { tournament: Tour }) {
  const { t } = useI18n()
  const mutation = useAction()
  const [teams, setTeams] = useState<[string, string][]>(tournament.teams.map(team => [team[0]?.id ?? '', team[1]?.id ?? '']))
  function change(cohort: number, member: number, next: string) {
    setTeams(teams.map((team, i) => i !== cohort ? team : member === 0 ? [next, team[1]] : [team[0], next]))
  }
  return <form className="card-form no-frame" onSubmit={event => {
    event.preventDefault()
    mutation.mutate({ method: 'PUT', path: `/tournaments/${tournament.id}/teams`, body: { teams } })
  }}>
    {teams.map((team, row) => <fieldset key={row}><legend>{t('team')} {row + 1}</legend>
      <div className="form-grid">{team.map((value, col) => <label key={col}>{t('PLAYER')} {col + 1}
        <select required value={value} onChange={e => change(row, col, e.target.value)}>
          <option value="">{t('choosePlayer')}</option>{tournament.roster.map(user =>
            <option key={user.id} value={user.id} disabled={user.id !== value && teams.flat().includes(user.id)}>{user.display_name}</option>)}
        </select></label>)}</div>
      <button type="button" onClick={() => setTeams(teams.filter((_, i) => i !== row))}>{t('REMOVE')}</button>
    </fieldset>)}
    <div className="actions"><button type="button" disabled={teams.length >= Math.floor(tournament.roster.length / 2)}
      onClick={() => setTeams([...teams, ['', '']])}>{t('addTeam')}</button>
      <button className="primary" disabled={mutation.isPending}>{t('save')}</button></div>
    <Alert error={mutation.error} />
  </form>
}

function Management({ tournament, admin, prestart }: { tournament: Tour, admin: boolean, prestart: boolean }) {
  const { t } = useI18n()
  const root = `/tournaments/${tournament.id}`
  const [pending, setPending] = useState(false)
  const [roster, setRoster] = useState<PublicUser | null>(null)
  const [organizer, setOrganizer] = useState<PublicUser | null>(null)
  const [offset, setOffset] = useState(0)
  const navigate = useNavigate()
  const mutation = useAction()
  const applications = useData<Page<Model['ApplicationView']>>(root + '/applications' + params({ offset }))
  const onRoster = (id: string, action: Model['RosterAction']['action']) => mutation.mutate({
    path: `${root}/roster/${id}`, body: { action },
  }, { onSuccess: () => setRoster(null) })
  return <>
    <Panel title={t('applicationQueue')}>
      <Data query={applications}>{data => <>
        {data.items.length ? <ul className="clean-list">{data.items.map(item => <li className="split" key={item.player.id}>
          <PlayerLink user={item.player} /><Badge value={item.status} />
          {item.status === 'PENDING' && prestart && <div className="actions">
            <button disabled={mutation.isPending} onClick={() => onRoster(item.player.id, 'ACCEPT')}>{t('ACCEPT')}</button>
            <button disabled={mutation.isPending} onClick={() => onRoster(item.player.id, 'REJECT')}>{t('REJECT')}</button>
          </div>}
        </li>)}</ul> : <Empty />}
        <Pager offset={offset} total={data.total} onChange={setOffset} />
      </>}</Data>
    </Panel>
    {prestart && <>
      <Panel title={t('manageRoster')}>
        <ul className="clean-list">{tournament.roster.map(item => <li className="split" key={item.id}>
          <PlayerLink user={item} /><button disabled={mutation.isPending} onClick={() => onRoster(item.id, 'REMOVE')}>{t('REMOVE')}</button>
        </li>)}</ul>
        <PlayerPicker label={t('choosePlayer')} value={roster} onChange={setRoster} exclude={tournament.roster.map(item => item.id)} />
        <button className="primary" disabled={!roster || mutation.isPending} onClick={() => { if (roster) onRoster(roster.id, 'ADD') }}>{t('ADD')}</button>
      </Panel>
      {tournament.team_mode === 'FIXED_TEAMS' && <Panel title={t('teams')}>
        <TeamsForm key={tournament.version} tournament={tournament} />
      </Panel>}
    </>}
    {admin && <>
      <Panel title={t('manageOrganizers')}>
        <ul className="clean-list">{tournament.organizers.map(item => <li className="split" key={item.id}>
          <PlayerLink user={item} /><button disabled={mutation.isPending} onClick={() => mutation.mutate({
            path: `${root}/organizers/${item.id}`, method: 'DELETE',
          })}>{t('revoke')}</button>
        </li>)}</ul>
        <PlayerPicker label={t('choosePlayer')} value={organizer} onChange={setOrganizer} exclude={tournament.organizers.map(item => item.id)} />
        <button className="primary" disabled={!organizer || mutation.isPending} onClick={() => {
          if (organizer) mutation.mutate({ path: `${root}/organizers/${organizer.id}`, method: 'PUT' }, { onSuccess: () => setOrganizer(null) })
        }}>{t('appoint')}</button>
      </Panel>
      <div className="actions">
        {prestart && <Link className="button" to={`${root}/edit`}>{t('editTournament')}</Link>}
        {pending ? <section className="alert" role="alert"><p>{t('deleteTournamentPrompt')}</p>
          <div className="actions"><button className="danger" disabled={mutation.isPending} onClick={() =>
            mutation.mutate({ path: root, method: 'DELETE' }, { onSuccess: () => navigate('/tournaments') })}>{t('confirm')}</button>
          <button onClick={() => setPending(false)}>{t('cancel')}</button></div></section>
          : <button className="danger" onClick={() => setPending(true)}>{t('deleteTournament')}</button>}
      </div>
    </>}
    <Alert error={mutation.error} />
  </>
}

function TournamentDetail({ tournament, account }: { tournament: Tour, account: Account | null }) {
  const { t, language } = useI18n()
  const me = account?.password_change_required ? undefined : account?.user
  const admin = me?.role === 'ADMIN'
  const manager = admin || tournament.organizers.some(org => org.id === me?.id)
  const prestart = ['SCHEDULED', 'ACTION_REQUIRED'].includes(tournament.status)
  const registered = tournament.roster.some(u => u.id === me?.id)
  return <>
    <div className={`tournament-heading${tournament.cover_id ? ' with-cover' : ''}`}>
      <Heading title={tournament.title} subtitle={dateTime(language, tournament.starts_at, tournament.timezone)} action={<Badge value={tournament.status} />} />
      {tournament.cover_id && <img className="tour-cover" src={photoUrl(tournament.cover_id, 'full')} alt="" crossOrigin="anonymous" />}
    </div>
    <nav className="page-tabs" aria-label={tournament.title}>
      <a href="#roster">{t('roster')}</a><a href="#schedule">{t('schedule')}</a>
      {!!tournament.gallery.length && <a href="#gallery">{t('gallery')}</a>}
      {manager && <a href="#management">{t('manage')}</a>}
    </nav>
    <div className="stack">
      {tournament.description && <p className="description">{tournament.description}</p>}
      <div className="meta"><Badge value={tournament.format} /><Badge value={tournament.discipline} />
        {tournament.team_mode && <Badge value={tournament.team_mode} />}
        <span>{t('accepted')}: {tournament.accepted}/{tournament.capacity}</span>
        {tournament.completed_at && <time>{dateTime(language, tournament.completed_at, tournament.timezone)}</time>}
      </div>
      {tournament.status === 'ACTION_REQUIRED' && <p className="alert" role="status">{t('reschedule')}</p>}
      {me && !registered && prestart && <Signup tournament={tournament} />}
      <div className="form-grid" id="roster">
        <Panel title={t('roster')}><UserList users={tournament.roster} />
          {!!tournament.teams.length && <ul className="clean-list">{tournament.teams.map(team => <li className="team-label" key={team[0].id}>
            {team.map(player => <PlayerLink user={player} key={player.id} />)}
          </li>)}</ul>}</Panel>
        <Panel title={t('organizers')}><UserList users={tournament.organizers} /></Panel>
      </div>
      {!!tournament.standings.length && <Panel title={t('standings')}><Standings rows={tournament.standings} /></Panel>}
      {tournament.groups.map(group => <Panel key={group.id} title={`${t('group')} ${group.position}`}><Standings rows={group.standings} /></Panel>)}
      <div id="schedule"><Bracket tournament={tournament} /></div>
      {!tournament.standings.length && !!tournament.placements.length && <Panel title={t('placements')}><ul className="clean-list">
        {tournament.placements.map(place => <li key={place.players[0].id} className="split">
          <strong>{rankRange(place.rank, place.rank_end)}</strong><div className="team-label">
            {place.players.map(player => <PlayerLink user={player} key={player.id} />)}</div></li>)}
      </ul></Panel>}
      {manager && <Upload kind="tournament" owner={tournament.id} />}
      {!!tournament.gallery.length && <div id="gallery"><Gallery photos={tournament.gallery} admin={admin} tournamentId={tournament.id} /></div>}
      {manager && <section className="management" id="management"><Management tournament={tournament} admin={admin} prestart={prestart} /></section>}
    </div>
  </>
}

export function TournamentPage({ account, edit = false }: { account: Account | null, edit?: boolean }) {
  const { id } = useParams()
  const query = useData<Tour>(`/public/tournaments/${id}`)
  return <Data query={query}>{tournament => edit
    ? <TournamentForm key={tournament.version} tournament={tournament} />
    : <TournamentDetail tournament={tournament} account={account} />}</Data>
}
