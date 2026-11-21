// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import type { Model } from '../src/api'
import { HomePage } from '../src/pages/public'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function tournament(position: number): Model['TournamentSummary'] {
  return {
    id: `tournament-${position}`, title: `Tournament ${position}`, description: '',
    starts_at: new Date(Date.UTC(2030, 0, 1) + position * 3_600_000).toISOString(),
    timezone: 'UTC', completed_at: null, status: 'SCHEDULED', discipline: 'SINGLES',
    format: 'ROUND_ROBIN', team_mode: null, capacity: 8, accepted: 0,
    applications_open: true, cover_id: null,
  }
}

it.each([0, 1, 2, 3, 4, 5, 10_003])(
  'shows the nearest tournaments chronologically with bounded reads for %i scheduled tournaments',
  async total => {
    const reads: { offset: number, limit: number, returned: number }[] = []
    vi.stubGlobal('fetch', vi.fn(async input => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/public/tournaments') {
        expect(url.searchParams.get('status')).toBe('SCHEDULED')
        const offset = Number(url.searchParams.get('offset') ?? 0)
        const limit = Number(url.searchParams.get('limit') ?? 30)
        // Match the existing API's descending starts_at order and pagination.
        const items = Array.from({ length: Math.min(limit, Math.max(0, total - offset)) },
          (_, index) => tournament(total - offset - index))
        reads.push({ offset, limit, returned: items.length })
        return Response.json({ items, total })
      }
      if (['/api/v1/public/matches', '/api/v1/public/ratings'].includes(url.pathname)) {
        return Response.json({ items: [], total: 0 })
      }
      throw new Error(`Unexpected request: ${url}`)
    }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
    render(<QueryClientProvider client={client}><MemoryRouter><HomePage /></MemoryRouter></QueryClientProvider>)

    const expectedCount = Math.min(4, total)
    if (!total) await screen.findByText('No tournaments found. Try another search or status.')
    else await waitFor(() => expect(screen.queryAllByRole('link', { name: /^Tournament \d+/ })).toHaveLength(expectedCount))

    expect(screen.queryAllByRole('link', { name: /^Tournament \d+/ }).map(link => link.getAttribute('href')))
      .toEqual(Array.from({ length: expectedCount }, (_, index) => `/tournaments/tournament-${index + 1}`))
    expect(reads).toEqual([
      { offset: 0, limit: 4, returned: expectedCount },
      ...(total > 4 ? [{ offset: total - 4, limit: 4, returned: 4 }] : []),
    ])
    expect(reads.reduce((sum, read) => sum + read.returned, 0)).toBeLessThanOrEqual(8)
  },
)
