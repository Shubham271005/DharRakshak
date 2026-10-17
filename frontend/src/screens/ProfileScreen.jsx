/*
 * SCREEN: My crop — profile card, weather, registration form (F2 + C5)
 * OWNER:  Teammate 1
 * DATA:   getCropProfile, getWeather, getCurrentPosition, saveCropProfile
 *         (see docs/CONTRACT.md, row "Crop registration + profile card")
 *
 * This screen is fully working. POLISH TASKS for Teammate 1:
 *   [ ] Try it on a phone-width window and fix anything cramped.
 *   [ ] Ask a Hindi speaker to read every label in हिंदी mode; fix wording
 *       in shared/i18n/hi.json.
 *   [ ] Add a small crop icon/emoji next to the crop name in the card.
 *   [ ] Show "Saved ✓" for 3 seconds, then hide it automatically.
 *   [ ] Demo prep: register a second crop live, then switch back to the demo crop.
 */
import { useEffect, useState } from 'react'
import { ApiError, getCropProfile, getCurrentPosition, getWeather, saveCropProfile } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Button, Card, ErrorBox, Field, INPUT_CLASS, Loading, MockTag, Notice, ScreenHeader, SectionTitle } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate, todayISO } from '../lib/format.js'
import { CROP_OPTIONS, STAGE_LABELS, cropLabel, stageLabel } from '../lib/labels.js'

function Fact({ label, value }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-0.5 text-lg font-bold text-forest">{value}</p>
    </div>
  )
}

function ProfileCard({ profile }) {
  const { lang, t } = useLanguage()
  const harvest =
    profile.expected_harvest_start || profile.expected_harvest_end
      ? `${formatDate(profile.expected_harvest_start, lang)} – ${formatDate(profile.expected_harvest_end, lang)}`
      : '—'
  const yieldText = profile.yield_estimate
    ? `${profile.yield_estimate.min_kg}–${profile.yield_estimate.max_kg} kg`
    : t('range_pending')
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-2xl font-bold text-forest">
          {cropLabel(profile.crop_type, lang)}
          {profile.variety && <span className="ml-2 text-base font-normal text-muted">({profile.variety})</span>}
        </h2>
        <p className="text-sm text-muted">{profile.farmer_name}</p>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <Fact label={t('stage')} value={stageLabel(profile.stage, lang)} />
        <Fact label={t('day_count')} value={`${t('day')} ${profile.days_since_sowing}`} />
        <Fact label={t('area')} value={`${profile.area_acres} ${t('acres')}`} />
        <Fact label={t('location')} value={profile.location.name} />
        <Fact label={t('harvest_window')} value={harvest} />
        <Fact label={t('yield_estimate')} value={yieldText} />
      </div>
    </Card>
  )
}

function WeatherCard({ cropId }) {
  const { t, tr } = useLanguage()
  const { data: weather, loading, error } = useApiData(() => getWeather(cropId), [cropId])
  return (
    <Card>
      <div className="mb-3 flex items-center justify-between gap-2">
        <SectionTitle>{t('weather_title')}</SectionTitle>
        {weather?.source === 'mock' && <MockTag />}
      </div>
      {loading && <Loading />}
      {error && <p className="text-sm text-muted">{t('weather_unavailable')}</p>}
      {weather && (
        <>
          <div className="mb-3 grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-tint p-3">
              <p className="text-2xl">☔</p>
              <p className="font-bold text-forest">{weather.rain_last_3_days_mm} mm</p>
              <p className="text-xs text-muted">{t('rain_3_days')}</p>
            </div>
            <div className="rounded-xl bg-tint p-3">
              <p className="text-2xl">💧</p>
              <p className="font-bold text-forest">{Math.round(weather.avg_humidity_pct)}%</p>
              <p className="text-xs text-muted">{t('humidity')}</p>
            </div>
            <div className="rounded-xl bg-tint p-3">
              <p className="text-2xl">🌡</p>
              <p className="font-bold text-forest">{Math.round(weather.avg_temp_c)}°C</p>
              <p className="text-xs text-muted">{t('temperature')}</p>
            </div>
          </div>
          <p className="text-sm text-ink">{tr(weather.summary)}</p>
        </>
      )}
    </Card>
  )
}

const toForm = (p) => ({
  farmer_name: p.farmer_name,
  crop_type: p.crop_type,
  variety: p.variety ?? '',
  sowing_date: p.sowing_date,
  area_acres: p.area_acres,
  location_name: p.location.name,
  stage: p.stage,
  latitude: null,
  longitude: null,
})

function CropForm({ profile, cropId, onSaved }) {
  const { lang, t } = useLanguage()
  const [form, setForm] = useState(() => toForm(profile))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null) // {tone, text}
  const [locating, setLocating] = useState(false)

  useEffect(() => setForm(toForm(profile)), [profile])
  const set = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value, ...(field === 'location_name' ? { latitude: null, longitude: null } : {}) }))

  async function useMyLocation() {
    setLocating(true)
    try {
      const pos = await getCurrentPosition()
      setForm((f) => ({ ...f, ...pos }))
      setMessage({ tone: 'tint', text: t('location_captured') })
    } catch (err) {
      setMessage({ tone: 'rust', text: `${t('location_failed')} ${err.message}` })
    } finally {
      setLocating(false)
    }
  }

  async function save(asNew) {
    if (!form.farmer_name.trim()) {
      setMessage({ tone: 'rust', text: t('name_required') })
      return
    }
    setSaving(true)
    setMessage(null)
    try {
      const body = { ...form, area_acres: Number(form.area_acres), preferred_language: lang }
      if (body.latitude == null) {
        delete body.latitude
        delete body.longitude
      }
      const saved = await saveCropProfile(body, asNew ? null : cropId)
      onSaved(saved)
      setMessage({ tone: 'tint', text: asNew ? t('registered') : t('saved') })
    } catch (err) {
      setMessage({ tone: 'rust', text: err instanceof ApiError ? err.message : String(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <SectionTitle>{t('edit_crop')}</SectionTitle>
      <form onSubmit={(e) => { e.preventDefault(); save(false) }} className="grid gap-4 md:grid-cols-2">
        <Field label={t('farmer_name')}>
          <input className={INPUT_CLASS} value={form.farmer_name} onChange={set('farmer_name')} required />
        </Field>
        <Field label={t('crop')}>
          <select className={INPUT_CLASS} value={form.crop_type} onChange={set('crop_type')}>
            {Object.keys(CROP_OPTIONS).map((key) => <option key={key} value={key}>{cropLabel(key, lang)}</option>)}
          </select>
        </Field>
        <Field label={t('variety')} hint={t('variety_hint')}>
          <input className={INPUT_CLASS} value={form.variety} onChange={set('variety')} />
        </Field>
        <Field label={t('sowing_date')}>
          <input type="date" className={INPUT_CLASS} value={form.sowing_date} max={todayISO()} onChange={set('sowing_date')} required />
        </Field>
        <Field label={t('area_acres')}>
          <input type="number" min="0.1" step="0.1" className={INPUT_CLASS} value={form.area_acres} onChange={set('area_acres')} required />
        </Field>
        <Field label={t('stage')}>
          <select className={INPUT_CLASS} value={form.stage} onChange={set('stage')}>
            {Object.keys(STAGE_LABELS).map((key) => <option key={key} value={key}>{stageLabel(key, lang)}</option>)}
          </select>
        </Field>
        <div className="md:col-span-2">
          <Field label={t('village_district')} hint={form.latitude != null ? `📍 ${form.latitude}, ${form.longitude}` : t('village_hint')}>
            <div className="flex gap-2">
              <input className={INPUT_CLASS} value={form.location_name} onChange={set('location_name')} required />
              <Button variant="secondary" onClick={useMyLocation} disabled={locating} className="shrink-0">
                📍 {locating ? '…' : t('use_my_location')}
              </Button>
            </div>
          </Field>
        </div>
        {message && <Notice tone={message.tone} className="md:col-span-2">{message.text}</Notice>}
        <div className="flex flex-wrap gap-3 md:col-span-2">
          <Button type="submit" disabled={saving}>{saving ? t('saving') : t('save_changes')}</Button>
          <Button variant="secondary" onClick={() => save(true)} disabled={saving}>{t('register_new')}</Button>
        </div>
      </form>
    </Card>
  )
}

export default function ProfileScreen({ cropId, onCropChange }) {
  const { t } = useLanguage()
  const { data: profile, loading, error, reload } = useApiData(() => getCropProfile(cropId), [cropId])

  return (
    <section className="space-y-6">
      <ScreenHeader title={t('nav_profile')} subtitle={t('profile_subtitle')} />
      {loading && !profile && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {profile && (
        <>
          <div className="grid gap-6 lg:grid-cols-5">
            <div className="lg:col-span-3"><ProfileCard profile={profile} /></div>
            <div className="lg:col-span-2"><WeatherCard cropId={cropId} /></div>
          </div>
          <CropForm
            profile={profile}
            cropId={cropId}
            onSaved={(saved) => {
              if (saved.crop_id !== cropId) onCropChange(saved.crop_id)
              else reload()
            }}
          />
        </>
      )}
    </section>
  )
}
