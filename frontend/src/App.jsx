/*
 * App shell: navigation + the selected screen.
 *
 * Every screen receives the same props:
 *   cropId        — the farmer's current crop (string)
 *   onCropChange  — call with a new crop_id after registering a crop
 *   onNavigate    — switch to another screen by id (e.g. from the dashboard)
 *
 * Each screen is wrapped in an ErrorBoundary so one broken screen can't
 * take down the others.
 */
import { IndianRupee, LayoutDashboard, Leaf, MessageCircle, Sprout } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiError, demoCropId, getCropProfile } from './api/client.js'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { BottomNav, MobileHeader, Sidebar } from './components/Sidebar.jsx'
import AnalysisScreen from './screens/AnalysisScreen.jsx'
import ChatScreen from './screens/ChatScreen.jsx'
import DashboardScreen from './screens/DashboardScreen.jsx'
import FinanceScreen from './screens/FinanceScreen.jsx'
import ProfileScreen from './screens/ProfileScreen.jsx'

// Order here = order in the navigation. `labelKey` is a key in shared/i18n/*.json.
const SCREENS = [
  { id: 'dashboard', labelKey: 'nav_dashboard', Icon: LayoutDashboard, Component: DashboardScreen },
  { id: 'analysis', labelKey: 'nav_analysis', Icon: Leaf, Component: AnalysisScreen },
  { id: 'profile', labelKey: 'nav_profile', Icon: Sprout, Component: ProfileScreen },
  { id: 'finance', labelKey: 'nav_finance', Icon: IndianRupee, Component: FinanceScreen },
  { id: 'chat', labelKey: 'nav_chat', Icon: MessageCircle, Component: ChatScreen },
]

// The current screen is kept in the URL hash (e.g. http://localhost:5173/#finance)
// so refreshing the page — or sharing the link in a demo — keeps the screen.
const screenFromHash = () => {
  const id = window.location.hash.slice(1)
  return SCREENS.some((s) => s.id === id) ? id : 'dashboard'
}

// The selected crop is remembered in this browser so a refresh keeps it.
const CROP_KEY = 'dharrakshak.crop'
const savedCropId = () => {
  try {
    return localStorage.getItem(CROP_KEY) || demoCropId()
  } catch {
    return demoCropId()
  }
}

export default function App() {
  const [screenId, setScreenId] = useState(screenFromHash)
  const [cropId, setCropId] = useState(savedCropId)

  useEffect(() => {
    try {
      localStorage.setItem(CROP_KEY, cropId)
    } catch {
      /* storage blocked — the choice just won't survive a refresh */
    }
  }, [cropId])

  // If the remembered crop no longer exists (e.g. after scripts/reset_db.py),
  // fall back to the demo crop instead of showing errors everywhere.
  useEffect(() => {
    if (cropId === demoCropId()) return
    getCropProfile(cropId).catch((err) => {
      if (err instanceof ApiError && err.status === 404) setCropId(demoCropId())
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Keep the URL and the screen in sync (also handles browser Back/Forward).
  useEffect(() => {
    if (window.location.hash.slice(1) !== screenId) window.location.hash = screenId
    window.scrollTo({ top: 0 })
  }, [screenId])
  useEffect(() => {
    const onHashChange = () => setScreenId(screenFromHash())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const { Component } = SCREENS.find((s) => s.id === screenId)

  return (
    <div className="min-h-screen md:flex">
      <Sidebar screens={SCREENS} current={screenId} onSelect={setScreenId} />
      <div className="min-w-0 flex-1">
        <MobileHeader />
        <main className="mx-auto w-full max-w-[1760px] px-4 pb-24 pt-4 md:px-6 md:pb-8 md:pt-6 xl:px-10">
          {/* `key` resets the error boundary when you switch screens */}
          <ErrorBoundary key={screenId}>
            <Component cropId={cropId} onCropChange={setCropId} onNavigate={setScreenId} />
          </ErrorBoundary>
        </main>
      </div>
      <BottomNav screens={SCREENS} current={screenId} onSelect={setScreenId} />
    </div>
  )
}
