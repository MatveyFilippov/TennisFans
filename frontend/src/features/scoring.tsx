import type { Model, Rules } from '../api'
import { useI18n } from '../i18n'
import { blank, resultDraft, type Draft, type DraftSet } from './score-draft'

export const standardRules: Rules = {
  format: 'STANDARD_MATCH', deciding_match_tiebreak: false,
  short_games: 3, short_finish: 'DECIDING_GAME', short_tiebreak_points: 7,
}

export function RulesFields({ value, onChange }: { value: Rules, onChange: (rules: Rules) => void }) {
  const { t } = useI18n()
  const set = (patch: Partial<Rules>) => onChange({ ...value, ...patch })
  return <fieldset><legend>{t('scoring')}</legend>
    <label>{t('format')}<select value={value.format} onChange={e => set({
      format: e.target.value as Model['ScoreFormat'], deciding_match_tiebreak: false,
    })}>{(['STANDARD_MATCH', 'SINGLE_SET', 'SHORT_MATCH'] as const).map(v => <option key={v} value={v}>{t(v)}</option>)}</select></label>
    {value.format === 'STANDARD_MATCH' && <label className="check"><input type="checkbox" checked={value.deciding_match_tiebreak}
      onChange={e => set({ deciding_match_tiebreak: e.target.checked })} />{t('matchTiebreak')}</label>}
    {value.format === 'SHORT_MATCH' && <>
      <div className="form-grid">
        <label>{t('shortGames')}<input required type="number" min={2} max={20} value={value.short_games}
          onChange={e => set({ short_games: Number(e.target.value) })} /></label>
        <label>{t('shortFinish')}<select value={value.short_finish} onChange={e => set({ short_finish: e.target.value as Model['ShortFinish'] })}>
          {['DECIDING_GAME', 'TIEBREAK', 'WIN_BY_TWO'].map(v => <option key={v} value={v}>{t(v)}</option>)}</select></label>
        {value.short_finish === 'TIEBREAK' && <label>{t('tiebreakTarget')}<input required type="number" min={3} max={21}
          value={value.short_tiebreak_points} onChange={e => set({ short_tiebreak_points: Number(e.target.value) })} /></label>}
      </div>
      <p className="muted">{t('shortExample')}</p>
    </>}
  </fieldset>
}

export function ScoreFields({ value, onChange, rules, tournament = false, technical = false, sideNames }: {
  value: Draft, onChange: (next: Draft) => void, rules: Rules, tournament?: boolean, technical?: boolean, sideNames?: [string, string],
}) {
  const { t } = useI18n()
  const scores = value.outcome === 'COMPETITIVE' || value.outcome === 'RETIREMENT'
  const maximum = rules.format === 'STANDARD_MATCH' ? 3 : 1
  const minimum = value.outcome === 'RETIREMENT' ? 0 : rules.format === 'STANDARD_MATCH' ? 2 : 1
  const changeScore = (position: number, key: keyof DraftSet, input: string) =>
    onChange({ ...value, sets: value.sets.map((set, i) => i === position ? { ...set, [key]: input } : set) })
  return <fieldset><legend>{t('score')}</legend>
    <p className="muted">{t(rules.format ?? 'STANDARD_MATCH')}{rules.format === 'SHORT_MATCH' && <> · {rules.short_games} · {t(rules.short_finish ?? 'DECIDING_GAME')}</>}</p>
    <div className="form-grid">
      <label>{t('playedAt')}<input required type="datetime-local" step="any" value={value.date} onChange={e => onChange({ ...value, date: e.target.value })} /></label>
      <label>{t('winner')}<select value={value.winner} onChange={e => onChange({ ...value, winner: e.target.value === '1' ? 1 : 0 })}>
        <option value="0">{sideNames?.[0] || t('sideA')}</option><option value="1">{sideNames?.[1] || t('sideB')}</option></select></label>
      {tournament && <label>{t('outcome')}<select value={value.outcome} onChange={e => {
        const outcome = e.target.value as Model['Outcome']
        onChange({ ...value, outcome, sets: outcome === 'RETIREMENT' ? [] : outcome === 'COMPETITIVE' && !value.sets.length ? resultDraft(rules).sets : value.sets })
      }}>{(technical ? ['WALKOVER', 'RETIREMENT', 'FORFEIT'] : ['COMPETITIVE', 'WALKOVER', 'RETIREMENT', 'FORFEIT']).map(v => <option key={v} value={v}>{t(v)}</option>)}</select></label>}
    </div>
    {scores && <>
      {value.sets.map((set, i) => <fieldset className="score-set" key={i}>
        <legend>{t('set')} {i + 1}</legend><div className="form-grid">
          {(['a', 'b', 'tiebreak_a', 'tiebreak_b'] as const).map((key, index) => <label key={key}>
            {t(['gamesA', 'gamesB', 'tiebreakA', 'tiebreakB'][index])}
            <input type="number" min={0} max={999} inputMode="numeric" value={set[key]} required={index < 2}
              onChange={e => changeScore(i, key, e.target.value)} />
          </label>)}
        </div>
      </fieldset>)}
      <div className="actions">
        {value.sets.length < maximum && <button type="button" onClick={() => onChange({ ...value, sets: [...value.sets, { ...blank }] })}>{t('addSet')}</button>}
        {value.sets.length > minimum && <button type="button" onClick={() => onChange({ ...value, sets: value.sets.slice(0, -1) })}>{t('removeSet')}</button>}
      </div>
    </>}
  </fieldset>
}
