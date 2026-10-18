/*
 * SCREEN: Dashboard — everything important at a glance
 * DATA:   getCropProfile, getLatestAnalysis, getWeather, getLoanSummary
 *
 * Quick questions open the chat with the question already sent
 * (handed over through sessionStorage key "chat.pending").
 */
import { ArrowRight, Calendar, Camera, Info, Ruler, CloudRain, Droplets, FileCheck2, Leaf, MapPin, MessageCircle, Sprout, Thermometer } from 'lucide-react'
import { getCropProfile, getLatestAnalysis, getLoanSummary, getWeather } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { CropSwitcher } from '../components/CropPicker.jsx'
import { Button, Card, ErrorBox, Loading, MockTag, Pill, ProgressBar, RiskBadge, Stat, WeatherTiles } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate, formatINR } from '../lib/format.js'
import { cropLabel, stageLabel } from '../lib/labels.js'

const QUICK_QUESTIONS = ['quick_q_risk', 'quick_q_today', 'quick_q_documents']

function LatestCheck({ cropId, onNavigate }) {
  const { lang, t, tr } = useLanguage()
  const { data: a, loading, error } = useApiData(() => getLatestAnalysis(cropId), [cropId])
  return (
    <Card
      title={t('latest_check_title')}
      icon={Leaf}
      action={<Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => onNavigate('analysis')}>{t('view_details')} <ArrowRight className="h-3.5 w-3.5" /></Button>}
      className="lg:col-span-2"
    >
      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {!loading && !error && !a && (
        <div className="flex flex-col items-start gap-3">
          <p className="text-sm text-muted">{t('no_analysis_yet')}</p>
          <Button icon={Camera} onClick={() => onNavigate('analysis')}>{t('check_leaf_cta')}</Button>
        </div>
      )}
      {a && (
        <div className="grid gap-4 sm:grid-cols-5">
          <div className="sm:col-span-2">
            <div className="mb-1 flex flex-wrap items-center gap-1.5">
              {a.is_demo && <MockTag labelKey="demo_example" />}
              <span className="text-[11px] text-muted">{formatDate(a.created_at, lang)}</span>
            </div>
            <p className="text-lg font-bold leading-snug text-forest">{tr(a.predictions[0].display_name)}</p>
            <p className="mb-2 text-xs text-muted">{Math.round(a.predictions[0].confidence * 100)}% · {t('model_confidence_short')}</p>
            <RiskBadge level={a.risk.level} size="lg" />
            {a.uncertain && <p className="mt-2 text-xs font-semibold text-gold">⚠ {t('result_uncertain_short')}</p>}
            <Button icon={Camera} variant="secondary" className="mt-4" onClick={() => onNavigate('analysis')}>{t('check_leaf_cta')}</Button>
          </div>
          <div className="sm:col-span-3">
            <p className="mb-1.5 text-[11px] font-bold uppercase tracking-widest text-muted">{t('next_steps')}</p>
            <ol className="space-y-1.5">
              {[...a.action_cards].sort((x, y) => x.priority - y.priority).map((c) => (
                <li key={c.card_id} className="flex items-start gap-2 rounded-lg bg-cream/70 px-2.5 py-1.5 text-sm">
                  <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white ${c.priority === 1 ? 'bg-rust' : 'bg-gold'}`}>{c.priority}</span>
                  <span><span className="font-semibold text-forest">{tr(c.title)}</span> <span className="text-muted">— {tr(c.detail)}</span></span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </Card>
  )
}

function WeatherCard({ cropId }) {
  const { t, tr } = useLanguage()
  const { data: w, loading, error } = useApiData(() => getWeather(cropId), [cropId])
  return (
    <Card title={t('weather_title')} icon={CloudRain} action={w?.source === 'mock' ? <MockTag /> : null}>
      {loading && <Loading />}
      {error && <p className="text-sm text-muted">{t('weather_unavailable')}</p>}
      {w && (
        <>
          <WeatherTiles items={[
            { icon: CloudRain, label: t('rain_short'), value: `${w.rain_last_3_days_mm} mm` },
            { icon: Droplets, label: t('humidity'), value: `${Math.round(w.avg_humidity_pct)}%` },
            { icon: Thermometer, label: t('temperature'), value: `${Math.round(w.avg_temp_c)}°C` },
          ]} />
          <p className="mt-3 flex items-start gap-2 rounded-xl bg-sky-50 px-3 py-2.5 text-sm leading-relaxed text-sky-950 ring-1 ring-sky-200/60">
            <Info className="mt-0.5 h-4 w-4 shrink-0 text-sky-600" />{tr(w.summary)}
          </p>
        </>
      )}
    </Card>
  )
}

function CropCard({ profile, onNavigate }) {
  const { lang, t } = useLanguage()
  return (
    <Card title={t('crop_card_title')} icon={Sprout} className="lg:col-span-1"
      action={<Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => onNavigate('profile')}>{t('edit')}</Button>}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-lg font-bold text-forest">{cropLabel(profile.crop_type, lang)}</p>
        <Pill tone="tint">{stageLabel(profile.stage, lang)}</Pill>
      </div>
      <div className="grid gap-2">
        <Stat icon={Calendar} label={t('day_count')} value={`${t('day')} ${profile.days_since_sowing}`} />
        <Stat icon={Ruler} label={t('area')} value={`${profile.area_acres} ${t('acres')}`} />
        <Stat icon={MapPin} label={t('location')} value={profile.location.name} />
      </div>
    </Card>
  )
}

function LoanCard({ cropId, onNavigate }) {
  const { lang, t, tr } = useLanguage()
  const { data: loan, loading, error } = useApiData(() => getLoanSummary(cropId), [cropId])
  const done = loan ? loan.documents.filter((d) => d.submitted).length : 0
  return (
    <Card title={t('loan_card_title')} icon={FileCheck2} className="lg:col-span-1 xl:col-span-2"
      action={<Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => onNavigate('finance')}>{t('view_details')}</Button>}>
      {loading && <Loading />}
      {error?.status === 404 && <p className="text-sm text-muted">{t('no_loan_yet')}</p>}
      {error && error.status !== 404 && <ErrorBox error={error} />}
      {loan && (
        <>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="truncate text-sm font-semibold text-forest">{tr(loan.loan.display_name)}</p>
            {loan.data_source === 'mock' && <MockTag />}
          </div>
          <div className="mb-1 flex justify-between text-xs">
            <span className="font-semibold">{t('documents_progress').replace('{done}', done).replace('{total}', loan.documents.length)}</span>
            {loan.missing_document_codes.length > 0 && <span className="font-semibold text-rust">{t('docs_missing_count').replace('{count}', loan.missing_document_codes.length)}</span>}
          </div>
          <ProgressBar value={done / loan.documents.length} />
          <div className="mt-3 grid grid-cols-2 gap-2 xl:grid-cols-3">
            <div className="hidden xl:block"><Stat label={t('sanctioned')} value={formatINR(loan.loan.sanctioned_amount_inr)} /></div>
            <Stat label={t('outstanding')} value={formatINR(loan.loan.outstanding_amount_inr)} />
            <Stat label={t('next_repayment')} value={loan.loan.next_repayment ? formatINR(loan.loan.next_repayment.amount_inr) : '—'}
              sub={loan.loan.next_repayment ? formatDate(loan.loan.next_repayment.due_date, lang) : null} />
          </div>
        </>
      )}
    </Card>
  )
}

function AskCard({ onNavigate }) {
  const { t } = useLanguage()
  const ask = (key) => {
    try {
      sessionStorage.setItem('chat.pending', t(key))
    } catch {
      /* storage blocked — just open the chat */
    }
    onNavigate('chat')
  }
  return (
    <Card title={t('ask_card_title')} icon={MessageCircle} className="xl:col-span-2">
      <p className="mb-3 text-xs text-muted">{t('ask_card_hint')}</p>
      <div className="grid gap-2 xl:grid-cols-3">
        {QUICK_QUESTIONS.map((key) => (
          <button key={key} onClick={() => ask(key)}
            className="flex items-center justify-between gap-2 rounded-xl bg-tint/70 px-3 py-2 text-left text-sm font-medium text-forest transition hover:bg-tint">
            {t(key)} <ArrowRight className="h-3.5 w-3.5 shrink-0 text-moss" />
          </button>
        ))}
      </div>
    </Card>
  )
}

export default function DashboardScreen({ cropId, onCropChange, onNavigate }) {
  const { lang, t } = useLanguage()
  const { data: profile, loading, error, reload } = useApiData(() => getCropProfile(cropId), [cropId])

  return (
    <div>
      {/* Hero banner */}
      <header className="leaf-pattern relative mb-5 overflow-hidden rounded-3xl bg-gradient-to-br from-[#173322] via-forest to-moss p-5 text-cream shadow-xl shadow-forest/20 animate-rise sm:p-6">
        <div className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-leaf/25 blur-3xl" aria-hidden />
        <div className="pointer-events-none absolute -bottom-20 right-1/3 h-40 w-40 rounded-full bg-gold/20 blur-3xl" aria-hidden />
        <Sprout className="pointer-events-none absolute -bottom-4 right-4 h-32 w-32 text-white/[0.06]" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-medium text-leaf">{t('dashboard_subtitle')}</p>
            <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
              {profile ? t('greeting').replace('{name}', profile.farmer_name) : t('nav_dashboard')}
            </h1>
            {profile && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 font-semibold ring-1 ring-white/15">
                  <Sprout className="h-3.5 w-3.5 text-leaf" />{cropLabel(profile.crop_type, lang)} · {stageLabel(profile.stage, lang)}
                </span>
                <span className="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 ring-1 ring-white/15">
                  <Calendar className="h-3.5 w-3.5 text-leaf" />{t('day')} {profile.days_since_sowing}
                </span>
                <span className="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1 ring-1 ring-white/15">
                  <MapPin className="h-3.5 w-3.5 text-leaf" />{profile.location.name}
                </span>
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <CropSwitcher cropId={cropId} onCropChange={onCropChange} />
            <button onClick={() => onNavigate('analysis')}
              className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-gold to-[#e0bd4a] px-5 py-2.5 text-sm font-bold text-forest shadow-lg shadow-gold/30 transition hover:brightness-105 active:scale-[0.98]">
              <Camera className="h-4 w-4" />{t('check_leaf_cta')}
            </button>
          </div>
        </div>
      </header>
      {loading && !profile && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {profile && (
        <div className="stagger grid gap-4 lg:grid-cols-3 xl:grid-cols-4">
          <LatestCheck cropId={cropId} onNavigate={onNavigate} />
          <WeatherCard cropId={cropId} />
          <CropCard profile={profile} onNavigate={onNavigate} />
          <LoanCard cropId={cropId} onNavigate={onNavigate} />
          <AskCard onNavigate={onNavigate} />
        </div>
      )}
    </div>
  )
}
