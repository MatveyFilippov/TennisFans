import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { components } from './schema'
import type { Key } from './i18n'

export type Model = components['schemas']
export type Page<T> = { items: T[], total: number }
export type PublicUser = Model['PublicUser']
export type Match = Model['MatchView']
export type Tour = Model['TournamentView']
export type Account = Model['Account']
export type Score = Model['Score']
export type Rules = Model['Rules']
export type Action = { path: string, method?: 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: unknown, key?: string }

let base = ''
export async function configure(): Promise<string> {
  const response = await fetch('/config.json', { cache: 'no-store' })
  if (!response.ok) throw new ApiError('invalid_config')
  const config = await response.json() as { apiBaseUrl: string }
  const url = new URL(config.apiBaseUrl || location.origin)
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/' || url.search || url.hash) throw new ApiError('invalid_config')
  base = url.origin
  return base
}

export class ApiError extends Error {
  constructor(public code: string, public context: Record<string, unknown> = {}) {
    super(code)
  }
}

const errors: Record<string, Key> = {
  offline: 'offline', invalid_config: 'invalidConfig', validation: 'validation',
  username_taken: 'userTaken', invalid_credentials: 'invalidCredentials', invalid_password: 'invalidPassword',
  authentication_required: 'authentication', forbidden: 'forbidden', invalid_csrf: 'stale',
  stale_version: 'stale', invalid_score: 'invalidScore', invalid_participants: 'invalidParticipants',
  future_result: 'futureResult', premature_result: 'futureResult', not_found: 'notFound',
  file_too_large: 'fileTooLarge', request_too_large: 'fileTooLarge', invalid_image: 'invalidImage',
  media_quota: 'mediaQuota', rate_limited: 'rateLimit', capacity_full: 'capacityFull',
  capacity_below_roster: 'invalidTournament', invalid_configuration: 'invalidTournament',
  invalid_roster: 'invalidTournament', invalid_teams: 'invalidParticipants',
  applications_closed: 'applicationsClosed', roster_locked: 'rosterLocked',
  duplicate_application: 'duplicate', duplicate_member: 'duplicate', admin_cascade_required: 'adminCascade',
  cascade_confirmation: 'cascade',
}
export function errorKey(error: unknown): Key {
  if (error instanceof ApiError) return errors[error.code] ?? 'requestError'
  return 'requestError'
}

export function url(path: string): string {
  return base + '/api/v1' + path
}

export function photoUrl(id: string, variant: 'thumb' | 'full' = 'thumb'): string {
  return url(`/public/media/${id}/${variant}`)
}

export async function request<T>(path: string, action?: Action, csrf?: string): Promise<T> {
  if (action && !navigator.onLine) throw new ApiError('offline')
  const headers = new Headers()
  if (action?.key) headers.set('Idempotency-Key', action.key)
  if (csrf) headers.set('X-CSRF-Token', csrf)
  let body: BodyInit | undefined
  if (action?.body instanceof FormData) body = action.body
  else if (action?.body !== undefined) {
    body = JSON.stringify(action.body)
    headers.set('Content-Type', 'application/json')
  }
  try {
    const response = await fetch(url(path), {
      method: action ? action.method ?? 'POST' : 'GET',
      credentials: path.startsWith('/public/') ? 'omit' : 'include',
      headers, body,
    })
    if (!response.ok) {
      const error = await response.json().catch(() => ({})) as Partial<Model['ErrorBody']>
      throw new ApiError(error.code ?? 'request_error', error.context)
    }
    return (response.status === 204 ? undefined : await response.json()) as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError(navigator.onLine ? 'request_error' : 'offline')
  }
}

export function useData<T>(path: string, enabled = true) {
  return useQuery({ queryKey: [path], queryFn: () => request<T>(path), enabled })
}

export function useSession() {
  return useQuery({
    queryKey: ['/auth/session'],
    queryFn: () => request<Account>('/auth/session').catch(error => {
      if (error instanceof ApiError && error.code === 'authentication_required') return null
      throw error
    }),
  })
}

export function useAction<T = void>() {
  const cache = useQueryClient()
  return useMutation({
    networkMode: 'always',
    mutationFn: (action: Action) => request<T>(action.path, action, cache.getQueryData<Account | null>(['/auth/session'])?.csrf),
    onSuccess: async (result, action) => {
      if (['/auth/login', '/auth/register', '/auth/password'].includes(action.path)) {
        cache.setQueryData(['/auth/session'], result)
      }
      if (action.path === '/auth/logout') {
        cache.removeQueries({ predicate: query => !String(query.queryKey[0]).startsWith('/public/') })
        cache.setQueryData(['/auth/session'], null)
      }
      await cache.invalidateQueries()
    },
  })
}

export function params(values: Record<string, string | number | undefined>) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  return `?${query.toString()}`
}
