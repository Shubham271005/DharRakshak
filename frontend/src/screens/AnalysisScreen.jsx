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
import { AlertTriangle, BookOpen, Camera, CheckCircle2, CloudRain, Eye, History, ImageUp, Lightbulb, ListChecks, Loader2, ScanSearch, ShieldAlert } from 'lucide-react'
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

const RISK_GLOW = {
  elevated: 'bg-gradient-to-br from-rust/10 via-white to-white ring-1 ring-rust/15',
  moderate: 'bg-gradient-to-br from-gold/15 via-white to-white ring-1 ring-gold/20',
  low: 'bg-gradient-to-br from-leaf/15 via-white to-white ring-1 ring-leaf/20',
}

function Result({ result }) {
  const { lang, t, tr } = useLanguage()
  const cards = [...result.action_cards].sort((a, b) => a.priority - b.priority)
  return (
    <div className="stagger space-y-4">
      {/* Headline: top possibility + risk, tinted by risk level */}
      <Card className={RISK_GLOW[result.risk.level] ?? ''}>
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
          <div key={card.card_id} className="flex flex-col rounded-xl border border-black/5 bg-gradient-to-b from-white to-cream/60 p-3 transition duration-200 hover:-translate-y-0.5 hover:shadow-md">
            <div className="mb-1.5 flex items-start gap-2">
              <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${card.priority === 1 ? 'bg-rust' : 'bg-gold'}`}>{card.priority}</span>
              <h3 className="text-sm font-semibold leading-snug text-forest">{tr(card.title)}</h3>
            </div>
            <p className="flex-1 text-sm leading-snug">{tr(card.detail)}</p>
            <p className="mt-2.5 flex items-start gap-1.5 border-t border-black/5 pt-2 text-xs leading-relaxed text-muted">
              <Lightbulb className="mt-px h-3.5 w-3.5 shrink-0 text-gold" aria-hidden />
              <span><span className="font-semibold text-moss">{t('why')}</span> {tr(card.why)}</span>
            </p>
          </div>
        ))}
      </Card>

      <Card title={t('why_title')} icon={Lightbulb}>
        <div className="grid gap-3 md:grid-cols-3">
          {result.explanation.about && (
            <div className="rounded-xl bg-emerald-50/70 p-3 ring-1 ring-emerald-200/60">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-emerald-800">
                <BookOpen className="h-3.5 w-3.5" aria-hidden />{t('about_disease')}
              </p>
              <p className="text-sm leading-relaxed">{tr(result.explanation.about)}</p>
            </div>
          )}
          {result.explanation.look_for && (
            <div className="rounded-xl bg-sky-50/70 p-3 ring-1 ring-sky-200/60">
              <p className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-sky-800">
                <Eye className="h-3.5 w-3.5" aria-hidden />{t('look_for_signs')}
              </p>
              <p className="text-sm leading-relaxed">{tr(result.explanation.look_for)}</p>
            </div>
          )}
          <div className={`rounded-xl bg-amber-50/70 p-3 ring-1 ring-amber-200/60 ${result.explanation.about ? '' : 'md:col-span-3'}`}>
            <p className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-amber-800">
              <ShieldAlert className="h-3.5 w-3.5" aria-hidden />{t('risk_reasoning')}
            </p>
            <p className="text-sm leading-relaxed">{tr(result.explanation.summary)}</p>
          </div>
        </div>
        <Notice tone="gold" icon={AlertTriangle} className="mt-3 font-semibold">{tr(result.explanation.verify)}</Notice>
      </Card>
    </div>
  )
}

function HistoryCard({ history, currentId, onOpen }) {
  const { lang, t, tr } = useLanguage()
  if (history.length === 0) return null
  return (
    <Card title={`${t('history_title')} · ${history.length}`} icon={History} bodyClassName="p-3">
      <ul className="grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-3">
        {history.slice(0, 9).map((a) => {
          const top = a.predictions[0]
          const next = [...a.action_cards].sort((x, y) => x.priority - y.priority)[0]
          const active = a.analysis_id === currentId
          return (
            <li key={a.analysis_id}>
              <button onClick={() => onOpen(a)}
                className={`group/h flex h-full w-full flex-col gap-1.5 rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:shadow-md ${
                  active ? 'border-moss/40 bg-tint/50 ring-1 ring-moss/20' : 'border-black/5 bg-gradient-to-b from-white to-cream/50'}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-medium text-muted">{formatDate(a.created_at, lang)}</span>
                  <RiskBadge level={a.risk.level} />
                </div>
                <p className="font-semibold leading-snug text-forest">{tr(top.display_name)}</p>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-tint">
                    <div className="h-full rounded-full bg-gradient-to-r from-leaf to-moss" style={{ width: `${Math.round(top.confidence * 100)}%` }} />
                  </div>
                  <span className="text-[11px] font-semibold tabular-nums text-muted">{Math.round(top.confidence * 100)}% {t('model_confidence_short2')}</span>
                </div>
                {next && (
                  <p className="truncate text-xs text-muted">
                    <span className="font-semibold text-moss">{t('next_step_short')}:</span> {tr(next.title)}
                  </p>
                )}
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

export default function AnalysisScreen({ cropId }) {
  const { t } = useLanguage()
  const { data: history, loading, error, reload } = useApiData(() => getHistory(cropId), [cropId])
  const [fresh, setFresh] = useState(null)
  useEffect(() => setFresh(null), [cropId])
  const result = fresh  // nothing is shown until a photo is checked or an earlier check is opened

  return (
    <section>
      <ScreenHeader title={t('nav_analysis')} subtitle={t('analysis_subtitle')} />
      <div className="grid items-start gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
        <UploadPanel cropId={cropId} onResult={(r) => { setFresh(r); reload() }} />
        <div className="min-w-0 space-y-4">
          {loading && !history && <Loading />}
          {error && <ErrorBox error={error} onRetry={reload} />}
          {result ? <Result result={result} /> : <Notice tone="tint">{t('upload_to_see_result')}</Notice>}
          {history && <HistoryCard history={history} currentId={result?.analysis_id} onOpen={setFresh} />}
        </div>
      </div>
    </section>
  )
}
