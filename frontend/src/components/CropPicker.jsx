/*
 * Every crop on this device, in two forms:
 *   <CropList>      "My crops" card (My crop screen): all crops with stage,
 *                   location, days since sowing, number of leaf checks and
 *                   the latest risk; tap one to switch to it.
 *   <CropSwitcher>  compact dropdown (Dashboard header) to switch crops.
 *
 * Both read GET /api/crops via listCrops(). Pass a changing `refreshKey`
 * to reload the list (e.g. after registering a new crop).
 */
import { CheckCircle2, ChevronRight, Layers, MapPin, Sprout } from 'lucide-react'
import { listCrops } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate } from '../lib/format.js'
import { cropLabel, stageLabel } from '../lib/labels.js'
import { Card, ErrorBox, Loading, Pill, RiskBadge } from './ui.jsx'

export function CropList({ cropId, onCropChange, refreshKey = 0 }) {
  const { lang, t, tr } = useLanguage()
  const { data: crops, loading, error, reload } = useApiData(listCrops, [refreshKey])

  return (
    <Card
      title={t('my_crops_title')}
      icon={Layers}
      action={crops && <span className="text-xs text-muted">{t('crops_count').replace('{count}', crops.length)}</span>}
      bodyClassName="p-2"
    >
      {loading && !crops && <div className="px-2"><Loading /></div>}
      {error && <div className="p-2"><ErrorBox error={error} onRetry={reload} /></div>}
      {crops && (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {crops.map(({ profile: p, checks, latest_risk: risk, latest_prediction: pred, latest_check_at: at }) => {
            const current = p.crop_id === cropId
            return (
              <li key={p.crop_id}>
                <button
                  onClick={() => onCropChange(p.crop_id)}
                  aria-current={current ? 'true' : undefined}
                  className={`flex h-full w-full flex-col gap-1.5 rounded-xl border p-3 text-left transition ${
                    current ? 'border-moss bg-tint/50 ring-1 ring-moss/30' : 'border-black/5 bg-cream/40 hover:border-moss/40 hover:bg-white'
                  }`}
                >
                  <span className="flex w-full items-center justify-between gap-2">
                    <span className="flex min-w-0 items-center gap-2">
                      <Sprout className="h-4 w-4 shrink-0 text-moss" aria-hidden />
                      <span className="truncate font-semibold text-forest">{cropLabel(p.crop_type, lang)}</span>
                    </span>
                    {current
                      ? <span className="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-moss"><CheckCircle2 className="h-3.5 w-3.5" />{t('viewing')}</span>
                      : <ChevronRight className="h-4 w-4 shrink-0 text-muted" aria-hidden />}
                  </span>
                  <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted">
                    <Pill tone="tint">{stageLabel(p.stage, lang)}</Pill>
                    <span>{t('day')} {p.days_since_sowing}</span>
                    <span className="flex min-w-0 items-center gap-0.5"><MapPin className="h-3 w-3 shrink-0" /><span className="truncate">{p.location.name}</span></span>
                  </span>
                  {checks > 0 ? (
                    <span className="flex flex-wrap items-center justify-between gap-1.5 text-xs">
                      <span className="min-w-0 truncate text-ink">{tr(pred)}</span>
                      <RiskBadge level={risk} />
                    </span>
                  ) : (
                    <span className="text-xs italic text-muted">{t('no_checks_yet')}</span>
                  )}
                  <span className="text-[11px] text-muted">
                    {t('checks_count').replace('{count}', checks)}
                    {at && ` · ${t('last_check')} ${formatDate(at, lang)}`}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

export function CropSwitcher({ cropId, onCropChange }) {
  const { lang, t } = useLanguage()
  const { data: crops } = useApiData(listCrops, [])
  if (!crops || crops.length < 2) return null
  return (
    <label className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm shadow-sm ring-1 ring-black/5">
      <Sprout className="h-4 w-4 text-moss" aria-hidden />
      <span className="sr-only">{t('switch_crop')}</span>
      <select value={cropId} onChange={(e) => onCropChange(e.target.value)} aria-label={t('switch_crop')}
        className="max-w-[12rem] cursor-pointer truncate bg-transparent font-semibold text-forest outline-none">
        {crops.map(({ profile: p }) => (
          <option key={p.crop_id} value={p.crop_id}>
            {cropLabel(p.crop_type, lang)} · {p.location.name}
          </option>
        ))}
      </select>
    </label>
  )
}
