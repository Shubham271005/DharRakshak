// Like useState, but the value survives switching screens (and page reloads
// in the same tab) by saving it in sessionStorage. Useful for chat history.
//
//   const [history, setHistory] = useSessionState('chat.history', [])
import { useCallback, useEffect, useState } from 'react'

function read(key, fallback) {
  try {
    const saved = sessionStorage.getItem(key)
    return saved !== null ? JSON.parse(saved) : fallback
  } catch {
    return fallback
  }
}

export function useSessionState(key, initialValue) {
  const [state, setState] = useState(() => ({ key, value: read(key, initialValue) }))

  // When the key changes (e.g. the farmer switches crop) load THAT key's saved
  // value instead of carrying the previous one across. Done during render, so a
  // stale value is never written under the new key.
  if (state.key !== key) {
    setState({ key, value: read(key, initialValue) })
  }

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(state.value))
    } catch {
      /* storage blocked — value still works for this visit */
    }
  }, [key, state.value])

  // Stable identity, so callers can use it in an effect's dependency list.
  const setValue = useCallback((next) => {
    setState((s) => ({ key: s.key, value: typeof next === 'function' ? next(s.value) : next }))
  }, [])

  return [state.value, setValue]
}
