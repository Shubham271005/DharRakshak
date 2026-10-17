// Like useState, but the value survives switching screens (and page reloads
// in the same tab) by saving it in sessionStorage. Useful for chat history.
//
//   const [history, setHistory] = useSessionState('chat.history', [])
import { useEffect, useState } from 'react'

export function useSessionState(key, initialValue) {
  const [value, setValue] = useState(() => {
    try {
      const saved = sessionStorage.getItem(key)
      return saved !== null ? JSON.parse(saved) : initialValue
    } catch {
      return initialValue
    }
  })

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value))
    } catch {
      /* storage blocked — value still works for this visit */
    }
  }, [key, value])

  return [value, setValue]
}
