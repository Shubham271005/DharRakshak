/*
 * App shell: sidebar + the selected screen.
 *
 * Every screen receives the same props:
 *   cropId        — the farmer's current crop (string)
 *   onCropChange  — call with a new crop_id after registering a crop
 *
 * Screens are owned by teammates (see src/screens/*.jsx). Each is wrapped
 * in an ErrorBoundary so one unfinished screen can't break the others.
 */
import { useEffect, useState } from 'react'
import { demoCropId } from './api/client.js'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import Sidebar from './components/Sidebar.jsx'
import AnalysisScreen from './screens/AnalysisScreen.jsx'
import ChatScreen from './screens/ChatScreen.jsx'
import FinanceScreen from './screens/FinanceScreen.jsx'
import ProfileScreen from './screens/ProfileScreen.jsx'

// Order here = order in the sidebar. `labelKey` is a key in i18n/uiText.js.
const SCREENS = [
  { id: 'profile', labelKey: 'nav_profile', icon: '🌱', Component: ProfileScreen },
  { id: 'analysis', labelKey: 'nav_analysis', icon: '🍃', Component: AnalysisScreen },
  { id: 'finance', labelKey: 'nav_finance', icon: '₹', Component: FinanceScreen },
  { id: 'chat', labelKey: 'nav_chat', icon: '💬', Component: ChatScreen },
]

// The current screen is kept in the URL hash (e.g. http://localhost:5173/#finance)
// so refreshing the page — or sharing the link in a demo — keeps the screen.
const screenFromHash = () => {
  const id = window.location.hash.slice(1)
  return SCREENS.some((s) => s.id === id) ? id : 'profile'
}

export default function App() {
  const [screenId, setScreenId] = useState(screenFromHash)
  const [cropId, setCropId] = useState(demoCropId)

  // Keep the URL and the screen in sync (also handles browser Back/Forward).
  useEffect(() => {
    if (window.location.hash.slice(1) !== screenId) window.location.hash = screenId
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
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-10 md:py-10">
        {/* `key` resets the error boundary when you switch screens */}
        <ErrorBoundary key={screenId}>
          <Component cropId={cropId} onCropChange={setCropId} />
        </ErrorBoundary>
      </main>
    </div>
  )
}
