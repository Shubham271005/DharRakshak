/*
 * SCREEN: Leaf check — upload + analysis results (F1, F3, F2, F4)
 * OWNER:  Teammate 2
 * DATA:   analyzeImage, getHistory (see docs/CONTRACT.md, "Analysis results")
 *
 * Layout: upload panel on the left (sticky on desktop), results on the right.
 *
 * POLISH TASKS for Teammate 2:
 *   [ ] Pick 2–3 clear demo photos and test them with scripts/try_model.py.
 *   [ ] Make the history rows clickable to re-open an older result.
 *   [ ] Check every label in each language with a native speaker.
 */
import { AlertTriangle, Camera, CheckCircle2, CloudRain, History, ImageUp, Lightbulb, ListChecks, Loader2, ScanSearch, ShieldAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { analyzeImage, getHistory } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Button, Card, ErrorBox, Loading, MockTag, Notice, ProgressBar, RiskBadge, ScreenHeader } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate } from '../lib/format.js'

const MAX_UPLOAD_MB = 8

function UploadPanel({ onResult, cropId }) {
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
    <Card title={t('upload_title')} icon={ScanSearch} className="lg:sticky lg:top-6">
      <label className="group relative flex aspect-[4/3] w-full cursor-pointer items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-leaf/50 bg-cream/60 text-center transition hover:border-moss">
        {preview ? (
          <img src={preview} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="flex flex-col items-center gap-2 px-4 text-sm text-muted">
            <ImageUp className="h-8 w-8 text-moss/70" aria-hidden />
            {t('choose_photo')}
          </span>
        )}
        {busy && (
          <span className="absolute inset-0 flex items-center justify-center bg-forest/40 text-white">
            <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
          </span>
        )}
        {/* capture="environment" opens the back camera on phones */}
        <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={choose} />
      </label>
      <p className="mt-2 text-xs text-muted">{t('upload_tips')}</p>
      <Button icon={Camera} onClick={analyze} disabled={!file || busy} className="mt-3 w-full">
        {busy ? t('analyzing') : t('analyze')}
      </Button>
      {error && <div className="mt-3"><ErrorBox error={error} /></div>}
    </Card>
  )
}

function Result({ result }) {
  const { lang, t, tr } = useLanguage()
  const cards = [...result.action_cards].sort((a, b) => a.priority - b.priority)
  return (
    <div className="space-y-4">
      {/* Headline: top possibility + risk */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-1.5">
              {result.is_demo && <MockTag labelKey="demo_example" />}
              {result.weather?.source === 'mock' && <MockTag />}
              <span className="text-[11px] text-muted">{formatDate(result.created_at, lang)}</span>
            </div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">{t('most_likely')}</p>
            <p className="text-xl font-bold leading-snug text-forest">{tr(result.predictions[0].display_name)}</p>
          </div>
          <div className="text-right">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{t('risk_title')}</p>
            <RiskBadge level={result.risk.level} size="lg" />
          </div>
        </div>
        {result.uncertain && result.uncertainty_message && (
          <Notice tone="gold" icon={AlertTriangle} className="mt-3">{tr(result.uncertainty_message)}</Notice>
        )}
        {result.crop_mismatch && !result.uncertain && (
          <Notice tone="gold" icon={ShieldAlert} className="mt-3">{t('crop_mismatch_note')}</Notice>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title={t('possibilities')} icon={ListChecks}>
          <ul className="space-y-2.5">
            {result.predictions.map((p, i) => (
              <li key={p.label}>
                <div className="mb-1 flex justify-between gap-3 text-sm">
                  <span className={i === 0 ? 'font-semibold text-forest' : 'text-ink'}>{tr(p.display_name)}</span>
                  <span className="font-semibold tabular-nums">{p.confidence < 0.01 ? '<1%' : `${Math.round(p.confidence * 100)}%`}</span>
                </div>
                <ProgressBar value={p.confidence} tone={i === 0 ? 'moss' : 'leaf'} label={tr(p.display_name)} />
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-muted">{t('model_confidence_note')}</p>
        </Card>

        <Card title={t('why_risk')} icon={ShieldAlert}>
          <ul className="space-y-1.5 text-sm">
            {result.risk.reasons.map((r) => (
              <li key={r.code} className="flex gap-2">
                <span className="mt-0.5 h-fit shrink-0 rounded-md bg-tint px-1.5 py-0.5 text-[11px] font-bold leading-none text-moss">+{r.points}</span>
                <span className="leading-snug">{tr(r.text)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 flex items-start gap-1.5 rounded-lg bg-cream/70 p-2 text-[11px] leading-relaxed text-muted">
            <CloudRain className="mt-px h-3.5 w-3.5 shrink-0 text-moss" aria-hidden />
            {result.weather ? tr(result.weather.summary) : t('weather_unavailable')}
          </p>
        </Card>
      </div>

      <Card title={t('actions_title')} icon={CheckCircle2} bodyClassName="grid gap-3 md:grid-cols-3">
        {cards.map((card) => (
          <div key={card.card_id} className="flex flex-col rounded-xl border border-black/5 bg-cream/50 p-3">
            <div className="mb-1.5 flex items-start gap-2">
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${card.priority === 1 ? 'bg-rust' : 'bg-gold'}`}>{card.priority}</span>
              <h3 className="text-sm font-semibold leading-snug text-forest">{tr(card.title)}</h3>
            </div>
            <p className="flex-1 text-sm leading-snug">{tr(card.detail)}</p>
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer font-semibold text-moss">{t('why')}</summary>
              <p className="mt-1 leading-relaxed text-muted">{tr(card.why)}</p>
            </details>
          </div>
        ))}
      </Card>

      <Card title={t('why_title')} icon={Lightbulb} className="bg-tint/40">
        <p className="text-sm leading-relaxed">{tr(result.explanation.summary)}</p>
        <p className="mt-2 text-sm font-semibold text-forest">{tr(result.explanation.verify)}</p>
      </Card>
    </div>
  )
}

function HistoryCard({ history, currentId }) {
  const { lang, t, tr } = useLanguage()
  if (history.length < 2) return null
  return (
    <Card title={t('history_title')} icon={History} bodyClassName="p-0">
      <ul className="divide-y divide-tint text-sm">
        {history.slice(0, 8).map((a) => (
          <li key={a.analysis_id} className={`flex flex-wrap items-center justify-between gap-2 px-4 py-2 ${a.analysis_id === currentId ? 'bg-tint/40' : ''}`}>
            <span className="w-24 shrink-0 text-xs text-muted">{formatDate(a.created_at, lang)}</span>
            <span className="min-w-0 flex-1 truncate font-medium">{tr(a.predictions[0].display_name)}</span>
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
    <section>
      <ScreenHeader title={t('nav_analysis')} subtitle={t('analysis_subtitle')} />
      <div className="grid items-start gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <UploadPanel cropId={cropId} onResult={(r) => { setFresh(r); reload() }} />
        <div className="min-w-0 space-y-4">
          {loading && !history && <Loading />}
          {error && <ErrorBox error={error} onRetry={reload} />}
          {result ? <Result result={result} /> : !loading && <Notice tone="tint">{t('no_analysis_yet')}</Notice>}
          {history && <HistoryCard history={history} currentId={result?.analysis_id} />}
        </div>
      </div>
    </section>
  )
}
