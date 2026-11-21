import { useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, params, useAction, useData, type Account, type Action, type Match, type Model, type Page, type PublicUser } from '../api'
import { Gallery, Upload } from '../components/media'
import { Alert, Badge, Data, Heading, MatchList, Pager, Panel, PlayerLink, PlayerPicker, ScoreText, UserList } from '../components/ui'
import { RulesFields, ScoreFields, standardRules } from '../features/scoring'
import { resultDraft, serializeResult } from '../features/score-draft'
import { dateTime, useI18n } from '../i18n'

function useRequestKey() {
  const prior = useRef({ signature: '', key: '' })
  return (body: unknown) => {
    const signature = JSON.stringify(body)
    if (signature !== prior.current.signature) prior.current = { signature, key: crypto.randomUUID() }
    return prior.current.key
  }
}

export function MatchIndex() {
  const { t } = useI18n()
  const [paramsFromUrl] = useSearchParams()
  const [offset, setOffset] = useState(0)
  const [discipline, setDiscipline] = useState('')
  const [category, setCategory] = useState('')
  const query = useData<Page<Match>>('/public/matches' + params({
    discipline, category, player_id: paramsFromUrl.get('player') ?? undefined, offset,
  }))
  return <>
    <Heading title={t('matches')} subtitle={t('matchIntro')} action={<Link className="button primary" to="/friendlies/new">{t('newFriendly')}</Link>} />
    <div className="toolbar">
      <label>{t('category')}<select value={category} onChange={e => { setCategory(e.target.value); setOffset(0) }}>
        {['', 'FRIENDLY', 'TOURNAMENT'].map(key => <option value={key} key={key}>{t(key || 'all')}</option>)}</select></label>
      <label>{t('discipline')}<select value={discipline} onChange={e => { setDiscipline(e.target.value); setOffset(0) }}>
        {['', 'SINGLES', 'DOUBLES'].map(key => <option value={key} key={key}>{t(key || 'all')}</option>)}</select></label>
    </div>
    <Data query={query}>{data => <><MatchList items={data.items} /><Pager offset={offset} total={data.total} onChange={setOffset} /></>}</Data>
  </>
}

export function NewFriendly({ account }: { account: Account }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const mutation = useAction<Model['Ref']>()
  const key = useRequestKey()
  const [discipline, setDiscipline] = useState<Model['Discipline']>('SINGLES')
  const [rules, setRules] = useState(standardRules)
  const [draft, setDraft] = useState(() => resultDraft(standardRules))
  const [partner, setPartner] = useState<PublicUser | null>(null)
  const [other, setOther] = useState<PublicUser | null>(null)
  const [otherPartner, setOtherPartner] = useState<PublicUser | null>(null)
  const doubles = discipline === 'DOUBLES'
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!other || (doubles && (!partner || !otherPartner))) return
    const body = {
      ...serializeResult(draft), discipline, rules,
      a: [account.user.id, ...(doubles && partner ? [partner.id] : [])],
      b: [other.id, ...(doubles && otherPartner ? [otherPartner.id] : [])],
    }
    mutation.mutate({ path: '/matches/friendly', body, key: key(body) }, {
      onSuccess: data => navigate(`/matches/${data.id}`),
    })
  }
  return <>
    <Heading title={t('newFriendly')} subtitle={t('friendlyIntro')} />
    <form className="card-form match-form" onSubmit={submit}>
      <label>{t('discipline')}<select value={discipline} onChange={e => setDiscipline(e.target.value as Model['Discipline'])}>
        <option value="SINGLES">{t('SINGLES')}</option><option value="DOUBLES">{t('DOUBLES')}</option>
      </select></label>
      <div className="form-grid">
        <fieldset><legend>{t('sideA')}</legend><PlayerLink user={account.user} avatar />
          {doubles && <PlayerPicker label={t('partners')} value={partner} onChange={setPartner}
            exclude={[account.user.id, other?.id ?? '', otherPartner?.id ?? '']} />}
        </fieldset>
        <fieldset><legend>{t('sideB')}</legend>
          <PlayerPicker label={t('choosePlayer')} value={other} onChange={setOther}
            exclude={[account.user.id, ...(doubles ? [partner?.id ?? '', otherPartner?.id ?? ''] : [])]} />
          {doubles && <PlayerPicker label={t('secondOpponent')} value={otherPartner} onChange={setOtherPartner}
            exclude={[account.user.id, partner?.id ?? '', other?.id ?? '']} />}
        </fieldset>
      </div>
      <RulesFields value={rules} onChange={next => {
        if (next.format !== rules.format) setDraft(resultDraft(next))
        setRules(next)
      }} />
      <ScoreFields value={draft} onChange={setDraft} rules={rules} sideNames={[account.user.display_name, other?.display_name ?? '']} />
      <Alert error={mutation.error} />
      <button className="primary" disabled={mutation.isPending || !other || (doubles && (!partner || !otherPartner))}>{t(mutation.isPending ? 'saving' : 'submitScore')}</button>
    </form>
  </>
}

type Operation = 'result' | 'dispute' | 'resolve' | 'correct' | 'delete'
const operationKey = { result: 'submitScore', dispute: 'dispute', resolve: 'resolve', correct: 'correct', delete: 'deleteMatch' }

function MatchAction({ match, operation, admin, technical, onFinish }: {
  match: Match, operation: Operation, admin: boolean, technical: boolean, onFinish: (deleted: boolean) => void,
}) {
  const { t } = useI18n()
  const mutation = useAction<Model['Ref']>()
  const key = useRequestKey()
  const [draft, setDraft] = useState(() => {
    const initial = resultDraft(match.rules, match.played_at, match.score)
    return technical ? { ...initial, outcome: 'WALKOVER' as const } : initial
  })
  const [reason, setReason] = useState('')
  const [decision, setDecision] = useState<'UPHOLD' | 'REPLACE' | 'ANNUL'>('UPHOLD')
  const [pending, setPending] = useState<Action | null>(null)
  const showScore = operation === 'result' || operation === 'correct' || (operation === 'resolve' && decision === 'REPLACE')
  const confirmToken = mutation.error instanceof ApiError && mutation.error.code === 'cascade_confirmation'
    ? String(mutation.error.context.confirmation) : null
  const affected = mutation.error instanceof ApiError && Array.isArray(mutation.error.context.affected)
    ? mutation.error.context.affected as { match_id: string, has_result: boolean }[] : []
  function send(action: Action) {
    mutation.mutate(action, {
      onSuccess: () => {
        setPending(null)
        onFinish(operation === 'delete' || (operation === 'resolve' && decision === 'ANNUL'))
      },
    })
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const root = `/matches/${match.id}`
    const body = { version: match.version, ...(operation !== 'result' && { reason }) }
    let action: Action
    if (operation === 'dispute') action = { path: `${root}/disputes`, body }
    else if (operation === 'resolve') action = { path: `${root}/resolution`, body: {
      ...body, decision, ...(decision === 'REPLACE' && { replacement: serializeResult(draft) }),
    } }
    else if (operation === 'delete') action = { path: `/admin${root}/delete`, body }
    else if (operation === 'correct') action = { path: `/admin${root}`, method: 'PATCH', body: { ...body, ...serializeResult(draft) } }
    else action = { path: `${root}/result`, body: { ...body, ...serializeResult(draft) } }
    if (operation !== 'dispute') action.key = key(action.body)
    setPending(action)
    send(action)
  }
  return <Panel title={t(operationKey[operation])}>
    <form className="card-form no-frame" onSubmit={submit}>
      {operation === 'resolve' && <label>{t('outcome')}<select value={decision} onChange={e => setDecision(e.target.value as typeof decision)}>
        {(admin ? ['UPHOLD', 'REPLACE', 'ANNUL'] : ['UPHOLD', 'REPLACE']).map(option => <option key={option} value={option}>{t(option)}</option>)}
      </select></label>}
      {showScore && <ScoreFields value={draft} onChange={setDraft} rules={match.rules} tournament={match.category === 'TOURNAMENT'} technical={technical}
        sideNames={[match.a.map(u => u.display_name).join(' / '), match.b.map(u => u.display_name).join(' / ')]} />}
      {operation !== 'result' && <label>{t('disputeReason')}<textarea required minLength={3} maxLength={1200} value={reason} onChange={e => setReason(e.target.value)} /></label>}
      {operation === 'dispute' && <p className="muted">{t('disputeNote')}</p>}
      {confirmToken && pending ? <section className="alert" role="alert">
        <p>{affected.length ? t('cascade') : t('confirmPermanent')}</p>
        <ul>{affected.map(item => <li key={item.match_id}><Link to={`/matches/${item.match_id}`}>{item.match_id}</Link> · {t(item.has_result ? 'COMPLETED' : 'SCHEDULED')}</li>)}</ul>
        <button className="danger" disabled={mutation.isPending} type="button" onClick={() =>
          send({ ...pending, body: { ...(pending.body as object), confirmation: confirmToken } })}>{t('confirm')}</button>
      </section> : <Alert error={mutation.error} />}
      <button className={operation === 'delete' ? 'danger' : 'primary'} disabled={mutation.isPending}>{t(mutation.isPending ? 'saving' : operationKey[operation])}</button>
    </form>
  </Panel>
}

function MatchDetail({ match, account }: { match: Match, account: Account | null }) {
  const { t, language } = useI18n()
  const [action, setAction] = useState<Operation | null>(null)
  const navigate = useNavigate()
  const tournament = useData<Model['TournamentView']>(`/public/tournaments/${match.tournament_id}`, !!match.tournament_id && !!account)
  const me = account?.password_change_required ? undefined : account?.user
  const admin = me?.role === 'ADMIN'
  const a = match.a.some(u => u.id === me?.id)
  const b = match.b.some(u => u.id === me?.id)
  const author = match.author
  const assigned = tournament.data?.organizers.some(u => u.id === me?.id)
  const actions: Operation[] = []
  if (me && (a || b || admin) && match.status === 'SCHEDULED') actions.push('result')
  if (me && match.status === 'COMPLETED' && ((a && match.b.some(u => u.id === match.author_id)) ||
    (b && match.a.some(u => u.id === match.author_id)))) actions.push('dispute')
  if (me && match.status === 'DISPUTED' && (admin || (assigned && !a && !b))) actions.push('resolve')
  if (admin && match.status === 'COMPLETED') actions.push('correct')
  if (admin && match.status !== 'DISPUTED') actions.push('delete')
  const timestamp = match.played_at ?? match.scheduled_at
  return <>
    <Heading title={t(match.category)} action={<Badge value={match.status} />} />
    <div className="stack">
      <div className="match-summary panel">
        <div className="match-side"><p className="eyebrow">{t('sideA')}</p><UserList users={match.a} /></div>
        <div className="score-display"><ScoreText match={match} /></div>
        <div className="match-side"><p className="eyebrow">{t('sideB')}</p><UserList users={match.b} /></div>
      </div>
      <div className="meta"><Badge value={match.discipline} /><Badge value={match.rules.format ?? 'STANDARD_MATCH'} />
        {timestamp && <time>{dateTime(language, timestamp)}</time>}
        {match.tournament_id && <Link to={`/tournaments/${match.tournament_id}`}>{t('TOURNAMENT')}</Link>}
        {author && <>{t('recordedBy')} <PlayerLink user={author} /></>}
      </div>
      {!!match.rating?.length && <Panel title={t('elo')}><ul className="clean-list">{match.rating.map(point => <li key={point.user_id}>
        {[...match.a, ...match.b].find(u => u.id === point.user_id)?.display_name} · {new Intl.NumberFormat(language, {
          maximumFractionDigits: 2, signDisplay: 'always',
        }).format(point.delta)} · {Math.round(point.rating_after)}
      </li>)}</ul></Panel>}
      {!!match.disputes?.length && <Panel title={t('disputes')}><ul className="clean-list">{match.disputes.map(item => <li key={item.created_at}>
        <time>{dateTime(language, item.created_at)}</time><p>{item.reason}</p>
        {item.decision && <><Badge value={item.decision} /><p>{item.resolution_reason}</p>
          {item.resolved_at && <time>{dateTime(language, item.resolved_at)}</time>}
          {item.resolver_id && <Link to={`/players/${item.resolver_id}`}>{t('resolver')}</Link>}</>}
      </li>)}</ul></Panel>}
      {!!match.revisions?.length && <Panel title={t('resultHistory')}><ul className="clean-list">
        {match.revisions.map(item => <li key={item.created_at}>
          <PlayerLink user={item.actor} /> <time>{dateTime(language, item.created_at)}</time>
          <p>{item.reason}</p>
          <div className="form-grid">
            <div>{t('before')} <ScoreText match={{ ...match, score: item.before.score }} /></div>
            <div>{t('after')} <ScoreText match={{ ...match, score: item.after.score }} /></div>
          </div>
        </li>)}
      </ul></Panel>}
      {!!actions.length && <div className="actions">{actions.map(option => <button key={option} aria-pressed={action === option}
        onClick={() => setAction(action === option ? null : option)}>{t(operationKey[option])}</button>)}</div>}
      {action && actions.includes(action) && <MatchAction key={action + match.version} match={match} operation={action} admin={admin} technical={action === 'result' && admin && !a && !b}
        onFinish={removed => { setAction(null); if (removed) navigate(match.tournament_id ? `/tournaments/${match.tournament_id}` : '/matches') }} />}
      {(admin || a || b || assigned) && me && <Upload kind="match" owner={match.id} />}
      <Gallery photos={match.gallery ?? []} admin={admin} />
    </div>
  </>
}

export function MatchPage({ account }: { account: Account | null }) {
  const { id } = useParams()
  const query = useData<Match>(`/public/matches/${id}`)
  return <Data query={query}>{match => <MatchDetail match={match} account={account} />}</Data>
}
