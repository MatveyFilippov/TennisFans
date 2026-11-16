import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, configure, errorKey, params, photoUrl, request } from '../src/api'
import { blank, resultDraft, serializeResult } from '../src/features/score-draft'
import { browserLanguage, dateTime, localInputDate, messages, rankRange, translate } from '../src/i18n'

afterEach(() => vi.unstubAllGlobals())

describe('internationalization', () => {
  it('detects Russian variants, falls back, and has entries in both locales', () => {
    expect(browserLanguage('RU-ru')).toBe('ru')
    expect(browserLanguage('tr-TR')).toBe('en')
    expect(translate('ru', 'PLAYOFF')).toBe('Плей-офф')
    expect(translate('en', 'PLAYOFF')).toBe('Playoffs')
    expect(translate('ru', 'unknown')).toBe('unknown')
    expect(translate('en', 'toString')).toBe('toString')
    expect(Object.values(messages).every(pair => pair.every(Boolean))).toBe(true)
  })
  it('localizes dates and displays tied places', () => {
    const instant = new Date('2025-01-07T00:15:15.123Z')
    expect(dateTime('en', instant.toISOString(), 'UTC')).toContain('Jan')
    expect(dateTime('ru', instant.toISOString(), 'Europe/Moscow')).toContain('03:15')
    expect(localInputDate(instant)).toHaveLength(16)
    expect(localInputDate(instant, true)).toHaveLength(23)
    expect(rankRange(1, 1)).toEqual('1')
    expect(rankRange(3, 4)).toEqual('3–4')
  })
})

describe('scores', () => {
  it('starts with the required number of sets and preserves valid optional values', () => {
    expect(resultDraft({ format: 'STANDARD_MATCH' }).sets).toHaveLength(2)
    expect(resultDraft({ format: 'SINGLE_SET' }).sets).toEqual([blank])
    const draft = resultDraft({ format: 'STANDARD_MATCH' }, '2026-01-01T00:00:00.000Z', {
      outcome: 'COMPETITIVE', winner: 1, sets: [{ a: 0, b: 6 }, { a: 6, b: 7, tiebreak_a: 0, tiebreak_b: 7 }],
    })
    expect(draft.sets[1].tiebreak_a).toBe('0')
    expect(serializeResult(draft)).toEqual({
      played_at: '2026-01-01T00:00:00.000Z',
      score: { winner: 1, outcome: 'COMPETITIVE', sets: [
        { a: 0, b: 6, tiebreak_a: null, tiebreak_b: null },
        { a: 6, b: 7, tiebreak_a: 0, tiebreak_b: 7 },
      ] },
    })
  })
  it('omits games for a walkover and a forfeit', () => {
    const result = resultDraft({ format: 'SHORT_MATCH' })
    expect(serializeResult({ ...result, outcome: 'WALKOVER' }).score.sets).toEqual([])
    expect(serializeResult({ ...result, outcome: 'FORFEIT' }).score.sets).toEqual([])
    expect(serializeResult({ ...result, outcome: 'RETIREMENT', sets: [] }).score.sets).toEqual([])
  })
})

describe('API transport', () => {
  it('uses runtime configuration and a same-origin fallback', async () => {
    vi.stubGlobal('location', { origin: 'https://self.example' })
    const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ apiBaseUrl: '' }))
      .mockResolvedValueOnce(Response.json({ apiBaseUrl: 'https://other.example' }))
      .mockResolvedValueOnce(Response.json({ apiBaseUrl: 'ftp://ftp.example' }))
      .mockResolvedValueOnce(Response.json({ apiBaseUrl: 'https://other.example/api' }))
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
    vi.stubGlobal('fetch', fetcher)
    await expect(configure()).resolves.toBe('https://self.example')
    expect(photoUrl('photo')).toBe('https://self.example/api/v1/public/media/photo/thumb')
    await expect(configure()).resolves.toBe('https://other.example')
    expect(photoUrl('photo', 'full')).toBe('https://other.example/api/v1/public/media/photo/full')
    for (let i = 0; i < 3; i++) await expect(configure()).rejects.toMatchObject({ code: 'invalid_config' })
    expect(params({ q: 'a b', empty: '', zero: 0, unset: undefined })).toEqual('?q=a+b&zero=0')
  })
  it('isolates public requests and sends CSRF and idempotency for mutations', async () => {
    vi.stubGlobal('navigator', { onLine: true })
    const fetcher = vi.fn().mockResolvedValueOnce(Response.json({ total: 0 }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
      .mockResolvedValueOnce(Response.json({ ok: true }))
    vi.stubGlobal('fetch', fetcher)
    await expect(request('/public/users')).resolves.toEqual({ total: 0 })
    expect(fetcher.mock.calls[0][1].credentials).toEqual('omit')
    await expect(request('/matches', { path: '/matches', method: 'PATCH', body: { score: 2 }, key: 'key' }, 'csrf')).resolves.toBeUndefined()
    expect(fetcher.mock.calls[1][1]).toMatchObject({ credentials: 'include', method: 'PATCH', body: '{"score":2}' })
    expect(fetcher.mock.calls[1][1].headers.get('X-CSRF-Token')).toBe('csrf')
    expect(fetcher.mock.calls[1][1].headers.get('Idempotency-Key')).toBe('key')
    const form = new FormData()
    await request('/media/match/id', { path: '/media/match/id', body: form })
    expect(fetcher.mock.calls[2][1].body).toBe(form)
    expect(fetcher.mock.calls[2][1].method).toBe('POST')
  })
  it('reports structured errors, unstructured responses, and offline mutations', async () => {
    vi.stubGlobal('navigator', { onLine: true })
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(Response.json({ code: 'stale_version', context: { id: 1 } }, { status: 409 }))
      .mockResolvedValueOnce(new Response('down', { status: 503 }))
      .mockRejectedValueOnce(new Error('network')))
    await expect(request('/auth/session')).rejects.toMatchObject({ code: 'stale_version', context: { id: 1 } })
    await expect(request('/auth/session')).rejects.toMatchObject({ code: 'request_error' })
    await expect(request('/auth/session')).rejects.toMatchObject({ code: 'request_error' })
    vi.stubGlobal('navigator', { onLine: false })
    await expect(request('/private', { path: '/private' })).rejects.toMatchObject({ code: 'offline' })
    expect(errorKey(new ApiError('stale_version'))).toBe('stale')
    expect(errorKey(new ApiError('other'))).toBe('requestError')
    expect(errorKey(new Error('raw'))).toBe('requestError')
  })
})
