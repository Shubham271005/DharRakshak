/*
 * Catches crashes inside one screen so the rest of the app keeps working.
 * App.jsx wraps every screen in this. While teammates are building, a bug
 * in one screen shows a friendly message instead of a blank page.
 */
import { Component } from 'react'
import { useLanguage } from '../i18n/LanguageContext.jsx'

function CrashMessage({ error }) {
  const { t } = useLanguage()
  return (
    <div className="rounded-2xl border border-rust/30 bg-rust/10 p-5 text-rust" role="alert">
      <p className="font-bold">{t('screen_crashed')}</p>
      <pre className="mt-2 overflow-auto text-xs">{String(error?.message ?? error)}</pre>
    </div>
  )
}

export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Screen crashed:', error, info.componentStack)
  }

  render() {
    return this.state.error ? <CrashMessage error={this.state.error} /> : this.props.children
  }
}
