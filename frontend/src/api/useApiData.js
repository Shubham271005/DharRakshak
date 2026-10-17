/*
 * Load data from the API client with loading and error states built in.
 *
 *   const { data, loading, error, reload } =
 *     useApiData(() => getLoanSummary(cropId), [cropId])
 *
 * - `loader` is a function that returns a Promise (any api/client.js call).
 * - `deps` works like useEffect's list: when a value changes, data reloads.
 * - Call `reload()` after saving something to fetch fresh data.
 */
import { useCallback, useEffect, useState } from 'react'

export function useApiData(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let cancelled = false // ignore results that arrive after the screen changed
    setState((s) => ({ ...s, loading: true, error: null }))
    loader()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => !cancelled && setState({ data: null, loading: false, error }))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { ...state, reload }
}
