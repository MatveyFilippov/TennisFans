// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { request, useAction, useData, useSession, type Account } from '../src/api'

const account: Account = {
  user: { id: 'player', username: 'player', display_name: 'Player', active: true, role: 'PLAYER', rating: 1500 },
  csrf: 'session-csrf',
  password_change_required: false,
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function scope() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return { client, wrapper }
}

it('treats an expired or absent session as anonymous', async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json({ code: 'authentication_required' }, { status: 401 }))
  const { wrapper } = scope()
  const hook = renderHook(() => useSession(), { wrapper })
  await waitFor(() => expect(hook.result.current.data).toBeNull())
})

it('loads public reads by key and propagates upstream session errors', async () => {
  vi.mocked(fetch).mockImplementation(async input => String(input).endsWith('/auth/session')
    ? Response.json({ code: 'database_unavailable' }, { status: 503 })
    : Response.json({ total: 2 }))
  const { wrapper } = scope()
  const hook = renderHook(() => ({
    list: useData('/public/users'), session: useSession(), unused: useData('/admin/audit', false),
  }), { wrapper })
  await waitFor(() => expect(hook.result.current.list.data).toEqual({ total: 2 }))
  await waitFor(() => expect(hook.result.current.session.error).toMatchObject({ code: 'database_unavailable' }))
  expect(hook.result.current.unused.fetchStatus).toBe('idle')
})

it('updates the active session and clears private cache leaving public entries after logout', async () => {
  let state: Account | null = null
  vi.mocked(fetch).mockImplementation(async (input, init) => {
    if (String(input).endsWith('/auth/login')) {
      state = account
      return Response.json(account)
    }
    if (String(input).endsWith('/auth/logout')) {
      expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('session-csrf')
      state = null
      return new Response(null, { status: 204 })
    }
    return state ? Response.json(state) : Response.json({ code: 'authentication_required' }, { status: 401 })
  })
  const { client, wrapper } = scope()
  const hook = renderHook(() => { useSession(); return useAction() }, { wrapper })
  await waitFor(() => expect(client.getQueryData(['/auth/session'])).toBeNull())
  await act(async () => { await hook.result.current.mutateAsync({ path: '/auth/login', body: {} }) })
  expect(client.getQueryData(['/auth/session'])).toEqual(account)
  client.setQueryData(['/account/notifications'], [])
  client.setQueryData(['/public/users'], [])
  await act(async () => { await hook.result.current.mutateAsync({ path: '/auth/logout' }) })
  expect(client.getQueryData(['/auth/session'])).toBeNull()
  expect(client.getQueryData(['/account/notifications'])).toBeUndefined()
  expect(client.getQueryData(['/public/users'])).toEqual([])
})

it('executes offline actions immediately as errors without sending or queuing them', async () => {
  vi.stubGlobal('navigator', { onLine: false })
  const { wrapper, client } = scope()
  client.setQueryData(['/auth/session'], account)
  const hook = renderHook(() => useAction(), { wrapper })
  await act(async () => {
    await expect(hook.result.current.mutateAsync({ path: '/matches/friendly', body: {} })).rejects.toMatchObject({ code: 'offline' })
  })
  expect(hook.result.current.isPaused).toBe(false)
  expect(vi.mocked(fetch).mock.calls.every(([, init]) => init?.method !== 'POST')).toBe(true)
  vi.mocked(fetch).mockRejectedValueOnce(new Error('disconnected'))
  await expect(request('/public/users')).rejects.toMatchObject({ code: 'offline' })
})
