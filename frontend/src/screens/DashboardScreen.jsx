/*
 * SCREEN: Dashboard — everything important at a glance
 * DATA:   getCropProfile, getLatestAnalysis, getWeather, getLoanSummary
 *
 * Quick questions open the chat with the question already sent
 * (handed over through sessionStorage key "chat.pending").
 */
import { ArrowRight, Camera, CloudRain, Droplets, FileCheck2, Leaf, MapPin, MessageCircle, Sprout, Thermometer } from 'lucide-react'
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
          <p className="mt-3 text-xs leading-relaxed text-ink">{tr(w.summary)}</p>
        </>
      )}
    </Card>
  )
}

function CropCard({ profile, onNavigate }) {
  const { lang, t } = useLanguage()
  return (
    <Card title={t('crop_card_title')} icon={Sprout}
      action={<Button variant="ghost" className="!px-2 !py-1 text-xs" onClick={() => onNavigate('profile')}>{t('edit')}</Button>}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-lg font-bold text-forest">{cropLabel(profile.crop_type, lang)}</p>
        <Pill tone="tint">{stageLabel(profile.stage, lang)}</Pill>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-sm">
        <div><dt className="text-[11px] uppercase tracking-wide text-muted">{t('day_count')}</dt><dd className="font-semibold">{t('day')} {profile.days_since_sowing}</dd></div>
        <div><dt className="text-[11px] uppercase tracking-wide text-muted">{t('area')}</dt><dd className="font-semibold">{profile.area_acres} {t('acres')}</dd></div>
        <div className="col-span-2"><dt className="text-[11px] uppercase tracking-wide text-muted">{t('location')}</dt>
          <dd className="flex items-center gap-1 font-semibold"><MapPin className="h-3.5 w-3.5 text-moss" />{profile.location.name}</dd></div>
      </dl>
    </Card>
  )
}

function LoanCard({ cropId, onNavigate }) {
  const { lang, t, tr } = useLanguage()
  const { data: loan, loading, error } = useApiData(() => getLoanSummary(cropId), [cropId])
  const done = loan ? loan.documents.filter((d) => d.submitted).length : 0
  return (
    <Card title={t('loan_card_title')} icon={FileCheck2}
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
          <div className="mt-3 grid grid-cols-2 gap-2">
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
    <Card title={t('ask_card_title')} icon={MessageCircle}>
      <p className="mb-3 text-xs text-muted">{t('ask_card_hint')}</p>
      <div className="flex flex-col gap-1.5">
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
  const { t } = useLanguage()
  const { data: profile, loading, error, reload } = useApiData(() => getCropProfile(cropId), [cropId])

  return (
    <div>
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-forest sm:text-2xl">
            {profile ? t('greeting').replace('{name}', profile.farmer_name) : t('nav_dashboard')}
          </h1>
          <p className="text-sm text-muted">{t('dashboard_subtitle')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CropSwitcher cropId={cropId} onCropChange={onCropChange} />
          <Button icon={Camera} onClick={() => onNavigate('analysis')}>{t('check_leaf_cta')}</Button>
        </div>
      </header>
      {loading && !profile && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {profile && (
        <div className="grid gap-4 lg:grid-cols-3">
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
