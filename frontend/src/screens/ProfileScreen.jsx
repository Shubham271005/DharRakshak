/*
 * SCREEN: My crop — profile summary, weather, edit / register form (F2 + C5)
 * OWNER:  Teammate 1
 * DATA:   getCropProfile, getWeather, getCurrentPosition, saveCropProfile
 *
 * POLISH TASKS for Teammate 1:
 *   [ ] Try it on a phone and fix anything cramped.
 *   [ ] Check every label in each language with a native speaker.
 *   [ ] Demo prep: register a second crop live, then switch back.
 */
import { CalendarDays, CloudRain, Droplets, LocateFixed, MapPin, Ruler, Save, Sprout, Thermometer, Wheat } from 'lucide-react'
import { useEffect, useState } from 'react'
import { ApiError, getCropProfile, getCurrentPosition, getWeather, saveCropProfile } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Button, Card, ErrorBox, Field, INPUT_CLASS, Loading, MockTag, Notice, Pill, ScreenHeader, Stat, WeatherTiles } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate, todayISO } from '../lib/format.js'
import { CROP_OPTIONS, STAGE_LABELS, cropLabel, stageLabel } from '../lib/labels.js'

function ProfileSummary({ profile }) {
  const { lang, t } = useLanguage()
  const harvest = profile.expected_harvest_start || profile.expected_harvest_end
    ? `${formatDate(profile.expected_harvest_start, lang)} – ${formatDate(profile.expected_harvest_end, lang)}`
    : '—'
  return (
    <Card title={t('crop_card_title')} icon={Sprout}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xl font-bold text-forest">
            {cropLabel(profile.crop_type, lang)}
            {profile.variety && <span className="ml-1.5 text-sm font-normal text-muted">({profile.variety})</span>}
          </p>
          <p className="text-xs text-muted">{profile.farmer_name}</p>
        </div>
        <Pill tone="tint">{stageLabel(profile.stage, lang)}</Pill>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        <Stat icon={CalendarDays} label={t('day_count')} value={`${t('day')} ${profile.days_since_sowing}`} />
        <Stat icon={Ruler} label={t('area')} value={`${profile.area_acres} ${t('acres')}`} />
        <Stat icon={MapPin} label={t('location')} value={profile.location.name} />
        <Stat icon={Wheat} label={t('harvest_window')} value={harvest} />
        <Stat icon={Sprout} label={t('yield_estimate')}
          value={profile.yield_estimate ? `${profile.yield_estimate.min_kg}–${profile.yield_estimate.max_kg} kg` : t('range_pending')} />
      </div>
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
          <p className="mt-3 text-xs leading-relaxed">{tr(w.summary)}</p>
        </>
      )}
    </Card>
  )
}

const toForm = (p) => ({
  farmer_name: p.farmer_name, crop_type: p.crop_type, variety: p.variety ?? '', sowing_date: p.sowing_date,
  area_acres: p.area_acres, location_name: p.location.name, stage: p.stage, latitude: null, longitude: null,
})

function CropForm({ profile, cropId, onSaved }) {
  const { lang, t } = useLanguage()
  const [form, setForm] = useState(() => toForm(profile))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null) // {tone, text}
  const [locating, setLocating] = useState(false)

  useEffect(() => setForm(toForm(profile)), [profile])
  const set = (field) => (e) =>
    setForm((f) => ({ ...f, [field]: e.target.value, ...(field === 'location_name' ? { latitude: null, longitude: null } : {}) }))

  async function useMyLocation() {
    setLocating(true)
    try {
      setForm({ ...form, ...(await getCurrentPosition()) })
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
      setTimeout(() => setMessage(null), 3000)
    } catch (err) {
      setMessage({ tone: 'rust', text: err instanceof ApiError ? err.message : String(err) })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card title={t('edit_crop')} icon={Save}>
      <form onSubmit={(e) => { e.preventDefault(); save(false) }} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label={t('farmer_name')}>
          <input className={INPUT_CLASS} value={form.farmer_name} onChange={set('farmer_name')} required />
        </Field>
        <Field label={t('crop')}>
          <select className={INPUT_CLASS} value={form.crop_type} onChange={set('crop_type')}>
            {Object.keys(CROP_OPTIONS).map((key) => <option key={key} value={key}>{cropLabel(key, lang)}</option>)}
          </select>
        </Field>
        <Field label={t('stage')}>
          <select className={INPUT_CLASS} value={form.stage} onChange={set('stage')}>
            {Object.keys(STAGE_LABELS).map((key) => <option key={key} value={key}>{stageLabel(key, lang)}</option>)}
          </select>
        </Field>
        <Field label={t('sowing_date')}>
          <input type="date" className={INPUT_CLASS} value={form.sowing_date} max={todayISO()} onChange={set('sowing_date')} required />
        </Field>
        <Field label={t('area_acres')}>
          <input type="number" min="0.1" step="0.1" className={INPUT_CLASS} value={form.area_acres} onChange={set('area_acres')} required />
        </Field>
        <Field label={t('variety')} hint={t('variety_hint')}>
          <input className={INPUT_CLASS} value={form.variety} onChange={set('variety')} />
        </Field>
        <div className="sm:col-span-2 lg:col-span-3">
          <Field label={t('village_district')} hint={form.latitude != null ? `📍 ${form.latitude}, ${form.longitude}` : t('village_hint')}>
            <div className="flex gap-2">
              <input className={INPUT_CLASS} value={form.location_name} onChange={set('location_name')} required />
              <Button variant="secondary" icon={LocateFixed} onClick={useMyLocation} disabled={locating} className="shrink-0">
                <span className="hidden sm:inline">{locating ? '…' : t('use_my_location')}</span>
              </Button>
            </div>
          </Field>
        </div>
        {message && <Notice tone={message.tone} className="sm:col-span-2 lg:col-span-3">{message.text}</Notice>}
        <div className="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-3">
          <Button type="submit" icon={Save} disabled={saving}>{saving ? t('saving') : t('save_changes')}</Button>
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
    <section className="space-y-4">
      <ScreenHeader title={t('nav_profile')} subtitle={t('profile_subtitle')} />
      {loading && !profile && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {profile && (
        <>
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="lg:col-span-3"><ProfileSummary profile={profile} /></div>
            <div className="lg:col-span-2"><WeatherCard cropId={cropId} /></div>
          </div>
          <CropForm profile={profile} cropId={cropId}
            onSaved={(saved) => (saved.crop_id !== cropId ? onCropChange(saved.crop_id) : reload())} />
        </>
      )}
    </section>
  )
}
