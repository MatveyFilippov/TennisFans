import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['tests/*.test.{ts,tsx}'],
    coverage: {
      include: ['src/api.ts', 'src/i18n.ts', 'src/features/score-draft.ts'],
      reporter: ['text', 'lcov'],
      thresholds: { lines: 75, statements: 75, branches: 75, functions: 75 },
    },
  },
})
