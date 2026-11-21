import type { Model, Rules, Score } from '../api'
import { localInputDate } from '../i18n'

export type DraftSet = { a: string, b: string, tiebreak_a: string, tiebreak_b: string }
export type Draft = { date: string, winner: 0 | 1, outcome: Model['Outcome'], sets: DraftSet[] }
export const blank: DraftSet = { a: '', b: '', tiebreak_a: '', tiebreak_b: '' }

export function resultDraft(rules: Pick<Rules, "format">, playedAt?: string | null, score?: Score | null): Draft {
  return {
    date: localInputDate(playedAt ? new Date(playedAt) : new Date(), true),
    winner: score?.winner ?? 0,
    outcome: score?.outcome ?? 'COMPETITIVE',
    sets: score?.sets?.map(item => ({
      a: String(item.a), b: String(item.b),
      tiebreak_a: item.tiebreak_a == null ? '' : String(item.tiebreak_a),
      tiebreak_b: item.tiebreak_b == null ? '' : String(item.tiebreak_b),
    })) ?? Array.from({ length: rules.format === 'STANDARD_MATCH' ? 2 : 1 }, () => ({ ...blank })),
  }
}

export function serializeResult(draft: Draft): { played_at: string, score: Score } {
  return {
    played_at: new Date(draft.date).toISOString(),
    score: {
      winner: draft.winner,
      outcome: draft.outcome,
      sets: draft.outcome === 'WALKOVER' || draft.outcome === 'FORFEIT' ? [] : draft.sets.map(set => ({
        a: Number(set.a), b: Number(set.b),
        tiebreak_a: set.tiebreak_a ? Number(set.tiebreak_a) : null,
        tiebreak_b: set.tiebreak_b ? Number(set.tiebreak_b) : null,
      })),
    },
  }
}
