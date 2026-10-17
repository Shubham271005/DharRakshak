/*
 * SCREEN: My crop — registration form + profile card (F2)
 * OWNER:  Teammate 1
 * DATA:   getCropProfile(cropId)          -> CropProfile   (read)
 *         getWeather(cropId)              -> Weather       (real, Open-Meteo)
 *         getCurrentPosition()            -> {latitude, longitude}  (phone GPS)
 *         saveCropProfile(form, cropId)   -> CropProfile   (edit this crop)
 *         saveCropProfile(form)           -> CropProfile   (register a new crop)
 *         Fields: docs/CONTRACT.md, row "Crop registration + profile card"
 *
 * ========================================================================
 * YOUR TASK — step by step (delete each TODO once it's done)
 * ========================================================================
 * Run the app:  cd frontend && npm run dev   → http://localhost:5173
 * The page updates automatically every time you save this file.
 *
 * TODO 1  Profile card. Replace <RawData> with a <Card> showing a grid
 *         (className="grid grid-cols-2 gap-4 md:grid-cols-3") of:
 *         crop (cropLabel(profile.crop_type, lang)), stage (stageLabel),
 *         day count (profile.days_since_sowing), area in acres,
 *         profile.location.name, harvest window
 *         (formatDate(profile.expected_harvest_start, lang) – end),
 *         yield (profile.yield_estimate ?? "Range pending").
 *         Small grey label on top (text-xs text-muted), big value below
 *         (text-lg font-bold text-forest).
 *
 * TODO 2  Registration form. Make a second <Card> with a <form>. Keep the
 *         values in one state object:
 *           const [form, setForm] = useState(null)
 *           // fill it once the profile loads:
 *           useEffect(() => { if (profile) setForm({ farmer_name: profile.farmer_name, ... }) }, [profile])
 *         Inputs (each with a <label>):
 *           farmer name ......... <input type="text">
 *           crop ................ <select> over Object.keys(CROP_OPTIONS)
 *           variety (optional) .. <input type="text">
 *           sowing date ......... <input type="date" max={todayISO()}>
 *           area in acres ....... <input type="number" min="0.1" step="0.1">
 *           village / district .. <input type="text">  → field name: location_name
 *           crop stage .......... <select> over Object.keys(STAGE_LABELS)
 *         Input style idea: "w-full rounded-xl border border-tint bg-cream px-3 py-2"
 *
 * TODO 3  Save. Two buttons:
 *           "Save changes"     → saveCropProfile({...form, preferred_language: lang}, cropId)
 *           "Register new crop" → saveCropProfile({...form, preferred_language: lang})
 *         In onSubmit: e.preventDefault(), await the call inside try/catch.
 *         On success: onCropChange(saved.crop_id), reload(), and show a
 *         green "Saved" message. On ApiError: show error.message in red.
 *         Disable the buttons while saving. Data is stored in the database,
 *         so it survives a server restart (api mode).
 *
 * TODO 3b Location. Next to the village field add a "📍 Use my location"
 *         button: `const pos = await getCurrentPosition()` and keep
 *         pos.latitude / pos.longitude in the form state (send them with
 *         saveCropProfile). If the farmer types a place instead, the backend
 *         looks it up — an unknown place returns ApiError status 422 whose
 *         message tells the farmer what to type; show it under the field.
 *
 * TODO 3c Weather card. Below the profile card, load
 *         useApiData(() => getWeather(cropId), [cropId]) and show
 *         tr(weather.summary) with a ☔ rain / 💧 humidity / 🌡 temperature
 *         row. On error (503) show "Weather unavailable right now" instead
 *         of the red error box.
 *
 * TODO 4  Language. Every label via t('your_key') — add the keys (en + hi)
 *         to src/i18n/uiText.js. Switch to हिंदी in the sidebar and check.
 *
 * DONE WHEN
 *   [ ] Card shows the demo profile (tomato, flowering, day 52, 0.5 acre).
 *   [ ] Saving the form updates the card.
 *   [ ] Empty name / future date shows a friendly error (the backend
 *       rejects future dates with a 422 in api mode).
 *   [ ] Works on a phone-width window and in both languages.
 */
import { getCropProfile } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { ErrorBox, Loading, RawData, ScreenHeader, StubBanner } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function ProfileScreen({ cropId }) {
  const { t } = useLanguage()
  const { data: profile, loading, error, reload } = useApiData(() => getCropProfile(cropId), [cropId])

  return (
    <section>
      <ScreenHeader title={t('nav_profile')} />
      <StubBanner owner="Teammate 1" />
      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {profile && <RawData data={profile} />}
    </section>
  )
}
