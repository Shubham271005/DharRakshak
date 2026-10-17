/*
 * SCREEN: Leaf check — upload + analysis results (F1, F3, F2, F4)
 * OWNER:  Teammate 2
 * DATA:   analyzeImage, getHistory (see docs/CONTRACT.md, row "Analysis results")
 *
 * This screen is fully working. POLISH TASKS for Teammate 2:
 *   [ ] Pick 2–3 demo photos (clear tomato leaves) and test them with
 *       `python scripts/try_model.py <photo>` before the presentation.
 *   [ ] Make the history list clickable to re-open an older result.
 *   [ ] Animate the confidence bars when a new result appears.
 *   [ ] Check every label in हिंदी mode with a Hindi speaker.
 */
import { useEffect, useMemo, useState } from 'react'
import { analyzeImage, getHistory } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Button, Card, ErrorBox, Loading, MockTag, Notice, ProgressBar, RiskBadge, ScreenHeader, SectionTitle } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

const MAX_UPLOAD_MB = 8

function UploadCard({ onResult, cropId }) {
  const { t } = useLanguage()
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview])

  function choose(e) {
    const picked = e.target.files?.[0]
    setError(null)
    if (picked && picked.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setError(new Error(t('photo_too_large')))
      return
    }
    setFile(picked ?? null)
  }

  async function analyze() {
    setBusy(true)
    setError(null)
    try {
      onResult(await analyzeImage(cropId, file))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <SectionTitle>{t('upload_title')}</SectionTitle>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <label className="flex h-40 w-full cursor-pointer items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed border-leaf/60 bg-cream text-center text-sm text-muted hover:border-moss sm:w-48">
          {preview ? <img src={preview} alt="" className="h-full w-full object-cover" /> : <span className="px-3">📷 {t('choose_photo')}</span>}
          {/* capture="environment" opens the back camera on phones */}
          <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={choose} />
        </label>
        <div className="flex-1 space-y-3">
          <p className="text-sm text-muted">{t('upload_tips')}</p>
          <Button onClick={analyze} disabled={!file || busy}>{busy ? t('analyzing') : t('analyze')}</Button>
          {error && <ErrorBox error={error} />}
        </div>
      </div>
    </Card>
  )
}

function Predictions({ result }) {
  const { t, tr } = useLanguage()
  return (
    <Card>
      <SectionTitle>{t('possibilities')}</SectionTitle>
      <ul className="space-y-3">
        {result.predictions.map((p, i) => (
          <li key={p.label}>
            <div className="mb-1 flex justify-between gap-3 text-sm">
              <span className={i === 0 ? 'font-bold text-forest' : 'text-ink'}>{tr(p.display_name)}</span>
              <span className="font-semibold tabular-nums">{p.confidence < 0.01 ? '<1%' : `${Math.round(p.confidence * 100)}%`}</span>
            </div>
            <ProgressBar value={p.confidence} tone={i === 0 ? 'moss' : 'leaf'} label={tr(p.display_name)} />
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">{t('model_confidence_note')}</p>
    </Card>
  )
}

function RiskCard({ result }) {
  const { t, tr } = useLanguage()
  return (
    <Card>
      <SectionTitle>{t('risk_title')}</SectionTitle>
      <RiskBadge level={result.risk.level} />
      <ul className="mt-4 space-y-2 text-sm">
        {result.risk.reasons.map((r) => (
          <li key={r.code} className="flex gap-2">
            <span className="mt-0.5 h-fit shrink-0 self-start rounded-full bg-tint px-2 py-0.5 text-xs font-bold leading-none text-moss">+{r.points}</span>
            <span>{tr(r.text)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-4 rounded-xl bg-cream p-3 text-xs text-muted">
        {result.weather ? <>🌦 {tr(result.weather.summary)}</> : t('weather_unavailable')}
      </p>
    </Card>
  )
}

function ActionCards({ cards }) {
  const { t, tr } = useLanguage()
  return (
    <div>
      <SectionTitle>{t('actions_title')}</SectionTitle>
      <div className="grid gap-4 md:grid-cols-3">
        {[...cards].sort((a, b) => a.priority - b.priority).map((card) => (
          <Card key={card.card_id} className="flex flex-col">
            <div className="mb-2 flex items-center gap-3">
              <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${card.priority === 1 ? 'bg-rust' : 'bg-gold'}`}>
                {card.priority}
              </span>
              <h3 className="font-bold text-forest">{tr(card.title)}</h3>
            </div>
            <p className="flex-1 text-sm">{tr(card.detail)}</p>
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer font-semibold text-moss">{t('why')}</summary>
              <p className="mt-1 text-muted">{tr(card.why)}</p>
            </details>
          </Card>
        ))}
      </div>
    </div>
  )
}

function Result({ result }) {
  const { t, tr } = useLanguage()
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        {result.is_demo && <MockTag labelKey="demo_example" />}
        {result.weather?.source === 'mock' && <MockTag />}
        <span className="text-xs text-muted">{new Date(result.created_at).toLocaleString()}</span>
      </div>
      {result.uncertain && result.uncertainty_message && <Notice tone="gold">⚠️ {tr(result.uncertainty_message)}</Notice>}
      {result.crop_mismatch && <Notice tone="gold">🔎 {t('crop_mismatch_note')}</Notice>}
      <div className="grid gap-6 lg:grid-cols-2">
        <Predictions result={result} />
        <RiskCard result={result} />
      </div>
      <ActionCards cards={result.action_cards} />
      <Card className="bg-tint">
        <SectionTitle>{t('why_title')}</SectionTitle>
        <p className="text-sm">{tr(result.explanation.summary)}</p>
        <p className="mt-3 text-sm font-bold text-forest">{tr(result.explanation.verify)}</p>
      </Card>
    </div>
  )
}

function History({ history, currentId }) {
  const { t, tr } = useLanguage()
  if (history.length < 2) return null
  return (
    <Card>
      <SectionTitle>{t('history_title')}</SectionTitle>
      <ul className="divide-y divide-tint text-sm">
        {history.slice(0, 8).map((a) => (
          <li key={a.analysis_id} className={`flex flex-wrap items-center justify-between gap-2 py-2 ${a.analysis_id === currentId ? 'font-semibold' : ''}`}>
            <span className="text-muted">{new Date(a.created_at).toLocaleDateString()}</span>
            <span className="flex-1 px-2">{tr(a.predictions[0].display_name)}</span>
            <RiskBadge level={a.risk.level} />
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function AnalysisScreen({ cropId }) {
  const { t } = useLanguage()
  const { data: history, loading, error, reload } = useApiData(() => getHistory(cropId), [cropId])
  const [fresh, setFresh] = useState(null)
  useEffect(() => setFresh(null), [cropId])

  const result = fresh ?? history?.[0] ?? null

  return (
    <section className="space-y-6">
      <ScreenHeader title={t('nav_analysis')} subtitle={t('analysis_subtitle')} />
      <UploadCard cropId={cropId} onResult={(r) => { setFresh(r); reload() }} />
      {loading && !history && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {result ? <Result result={result} /> : !loading && <Notice tone="tint">{t('no_analysis_yet')}</Notice>}
      {history && <History history={history} currentId={result?.analysis_id} />}
    </section>
  )
}
