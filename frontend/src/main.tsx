import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ApiError, configure } from './api'
import { Root } from './app/root'
import { browserLanguage, translate } from './i18n'
import './style.css'

const element = document.getElementById('root')!
const root = createRoot(element)
const language = browserLanguage(navigator.language)
root.render(<main><p role="status">{translate(language, 'loading')}</p></main>)
const client = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000, refetchInterval: 30_000, networkMode: 'always',
      retry: (n, error) => !(error instanceof ApiError) && n < 1,
    },
  },
})
configure().then(() => {
  root.render(<StrictMode><QueryClientProvider client={client}><Root /></QueryClientProvider></StrictMode>)
}).catch(() => {
  root.render(<main><p role="alert">{translate(language, 'invalidConfig')}</p>
    <button onClick={() => window.location.reload()}>{translate(language, 'retry')}</button></main>)
})
