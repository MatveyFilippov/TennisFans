import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState, type ReactNode } from 'react'
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useSession, type Account } from '../api'
import { Heading, Loading } from '../components/ui'
import { browserLanguage, I18n, translate, useI18n, type Language, type Theme } from '../i18n'
import { AccountPage, AdminPage, AuditPage, LoginPage } from '../pages/accounts'
import { MatchIndex, MatchPage, NewFriendly } from '../pages/matches'
import { ComparePage, Directory, HomePage, PlayerPage, TournamentIndex } from '../pages/public'
import { TournamentForm, TournamentPage } from '../pages/tournaments'

function Preferences({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    const saved = localStorage.getItem('tennisfans-language')
    return saved === 'ru' || saved === 'en' ? saved : browserLanguage(navigator.language)
  })
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = localStorage.getItem('tennisfans-theme')
    return saved === 'dark' || saved === 'light' ? saved : 'system'
  })
  const t = (key: string) => translate(language, key)
  useEffect(() => {
    document.documentElement.lang = language
    document.documentElement.dataset.theme = theme
  }, [language, theme])
  return <I18n.Provider value={{ language, t }}>
    {children}
    <div className="preferences">
      <label><span className="sr-only">{t('language')}</span>
        <select value={language} onChange={event => {
          const value = event.target.value as Language
          localStorage.setItem('tennisfans-language', value)
          setLanguage(value)
        }}>
          <option value="en">{t('english')}</option><option value="ru">{t('russian')}</option>
        </select>
      </label>
      <label><span className="sr-only">{t('theme')}</span>
        <select value={theme} onChange={event => {
          const value = event.target.value as Theme
          localStorage.setItem('tennisfans-theme', value)
          setTheme(value)
        }}>
          {['system', 'light', 'dark'].map(key => <option key={key} value={key}>{t(key)}</option>)}
        </select>
      </label>
    </div>
  </I18n.Provider>
}

function StatusLine() {
  const cache = useQueryClient()
  const { t } = useI18n()
  const [online, setOnline] = useState(navigator.onLine)
  const [stale, setStale] = useState(false)
  const [waiting, setWaiting] = useState<ServiceWorker | null>(null)
  useEffect(() => {
    function sync() {
      setOnline(navigator.onLine)
      if (navigator.onLine) setStale(false)
    }
    window.addEventListener('online', sync)
    window.addEventListener('offline', sync)
    return () => {
      window.removeEventListener('online', sync)
      window.removeEventListener('offline', sync)
    }
  }, [])
  useEffect(() => {
    if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
    const workers = navigator.serviceWorker
    let updating = false
    let registration: ServiceWorkerRegistration | undefined
    const onMessage = (event: MessageEvent) => {
      if (event.data === 'STALE_PUBLIC_DATA') setStale(true)
    }
    const onController = () => {
      void cache.invalidateQueries({ predicate: query => String(query.queryKey[0]).startsWith('/public/') })
      if (updating || waiting?.state === 'activated') window.location.reload()
    }
    const found = () => {
      registration?.installing?.addEventListener('statechange', event => {
        const worker = event.target as ServiceWorker
        if (worker.state === 'installed' && workers.controller) setWaiting(registration?.waiting ?? worker)
      })
    }
    workers.addEventListener('message', onMessage)
    workers.addEventListener('controllerchange', onController)
    void workers.register('/sw.js').then(value => {
      registration = value
      if (value.waiting) setWaiting(value.waiting)
      value.addEventListener('updatefound', found)
    }).catch(() => {})
    const markUpdate = () => { updating = true }
    window.addEventListener('tennisfans-update', markUpdate)
    return () => {
      workers.removeEventListener('message', onMessage)
      workers.removeEventListener('controllerchange', onController)
      registration?.removeEventListener('updatefound', found)
      window.removeEventListener('tennisfans-update', markUpdate)
    }
  }, [cache, waiting])
  return <>
    {(!online || stale) && <p className="status-line" role="status">{t(online ? 'stalePublic' : 'offline')}</p>}
    {waiting && <p className="status-line" role="status">{t('update')} <button onClick={() => {
      window.dispatchEvent(new Event('tennisfans-update'))
      waiting.postMessage('UPDATE')
    }}>{t('reload')}</button></p>}
  </>
}

function BrandLink() {
  const { t } = useI18n()
  return <Link to="/" className="brand" aria-label={t('brand')}>
    <img className="brand-mark" width="784" height="480" src="/brand/court-mark.svg" alt="" />
    <img className="brand-mark brand-mark-light" width="784" height="480" src="/brand/court-mark-light.svg" alt="" />
  </Link>
}

function Navigation({ account }: { account: Account | null }) {
  const { t } = useI18n()
  return <header className="site-header">
    <a href="#content" className="skip">{t('skip')}</a>
    <div className="nav-inner">
      <BrandLink />
      <nav className="main-nav" aria-label={t('mainNavigation')}>
        {([['matches', '/matches'], ['tournaments', '/tournaments'], ['players', '/players'], ['ratings', '/ratings']]).map(([label, path]) =>
          <NavLink to={path} key={path}>{t(label)}</NavLink>)}
      </nav>
      <nav className="account-nav" aria-label={t('account')}>
        {account && !account.password_change_required && account.user.role === 'ADMIN' && <NavLink to="/admin">{t('admin')}</NavLink>}
        <NavLink to={account ? '/account' : '/login'}>{t(account ? 'account' : 'signIn')}</NavLink>
      </nav>
    </div>
  </header>
}

function Body() {
  const { t } = useI18n()
  const location = useLocation()
  const session = useSession()
  const account = session.data ?? null
  const admin = account?.user.role === 'ADMIN' && !account.password_change_required
  const requireAccount = (render: (viewer: Account) => ReactNode, options: { admin?: boolean, allowReset?: boolean } = {}) => {
    if (session.isPending && navigator.onLine) return <Loading />
    if (!account) return <Navigate to="/login" replace state={{ from: location.pathname }} />
    if (account.password_change_required && !options.allowReset) return <Navigate to="/account" replace />
    if (options.admin && !admin) return <Heading title={t('forbidden')} />
    return render(account)
  }
  useEffect(() => {
    window.scrollTo(0, 0)
    document.getElementById('content')?.focus({ preventScroll: true })
  }, [location.pathname])
  return <div className={`app-shell${location.pathname === '/' ? ' home-shell' : ''}`}>
    <Navigation account={account} />
    <StatusLine />
    <main id="content" tabIndex={-1}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/players" element={<Directory />} />
        <Route path="/players/:id" element={<PlayerPage />} />
        <Route path="/ratings" element={<Directory ratings />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/matches" element={<MatchIndex />} />
        <Route path="/matches/:id" element={<MatchPage account={account} />} />
        <Route path="/friendlies/new" element={requireAccount(viewer => <NewFriendly account={viewer} />)} />
        <Route path="/tournaments" element={<TournamentIndex admin={admin} />} />
        <Route path="/tournaments/new" element={requireAccount(() => <TournamentForm />, { admin: true })} />
        <Route path="/tournaments/:id" element={<TournamentPage account={account} />} />
        <Route path="/tournaments/:id/edit" element={requireAccount(() => <TournamentPage account={account} edit />, { admin: true })} />
        <Route path="/login" element={<LoginPage key="login" />} />
        <Route path="/register" element={<LoginPage key="register" create />} />
        <Route path="/account" element={requireAccount(viewer => <AccountPage account={viewer} />, { allowReset: true })} />
        <Route path="/admin" element={requireAccount(() => <AdminPage />, { admin: true })} />
        <Route path="/admin/audit" element={requireAccount(() => <AuditPage />, { admin: true })} />
        <Route path="*" element={<Heading title={t('notFound')} action={<Link to="/">{t('home')}</Link>} />} />
      </Routes>
    </main>
    <footer className="site-footer"><div className="footer-inner">
      <BrandLink /><p>{t('footerLine')}</p>
    </div></footer>
  </div>
}

export function Root() {
  return <BrowserRouter><Preferences><Body /></Preferences></BrowserRouter>
}
