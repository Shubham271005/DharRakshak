/*
 * The ONLY place the frontend gets data from.
 *
 * Screens never call fetch() or read files themselves — they call these
 * functions. Every function is async and returns data shaped exactly like
 * shared/contract.py (see docs/CONTRACT.md).
 *
 * Two modes, set by VITE_API_MODE in frontend/.env:
 *   "mock" (default) — returns data from ../shared/sample_data.json after a
 *                      short fake delay, so loading states are visible.
 *                      No backend needed.
 *   "api"            — calls the FastAPI backend at /api/... (Vite forwards
 *                      it to http://localhost:8000).
 *
 * Switching modes never changes the screens.
 */
import sample from '../../../shared/sample_data.json'

export const API_MODE = import.meta.env.VITE_API_MODE === 'api' ? 'api' : 'mock'
export const isMockMode = () => API_MODE === 'mock'

/** Thrown for any failed request. `status` is the HTTP code (0 = network down). */
export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const MOCK_DELAY_MS = 300
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
// Return a deep copy so a screen can never accidentally edit the sample data.
const mockReturn = async (value) => {
  await wait(MOCK_DELAY_MS)
  return structuredClone(value)
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`/api${path}`, options)
  } catch {
    throw new ApiError('Cannot reach the DharRakshak server. Is the backend running on port 8000?')
  }
  if (!response.ok) {
    // FastAPI puts the reason in `detail` (a string, or a list for 422 errors).
    let message = `Request failed (${response.status})`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d) => d.msg).join('; ')
    } catch {
      /* body wasn't JSON */
    }
    throw new ApiError(message, response.status)
  }
  return response.json()
}

const postJSON = (path, body) =>
  request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

// ---------------------------------------------------------------------------
// System
// ---------------------------------------------------------------------------

/** The crop used throughout the demo. */
export const demoCropId = () => sample.crop_profile.crop_id

/** {status: "ok", stage: "..."} — used for the connection badge in api mode. */
export async function getHealth() {
  if (isMockMode()) return { status: 'ok', stage: 'mock' }
  return request('/health')
}

// ---------------------------------------------------------------------------
// F2 — crop profile (Teammate 1)
// ---------------------------------------------------------------------------

// Mock mode keeps the last saved profile here (lost on page reload).
let mockSavedProfile = null

export async function getCropProfile(cropId) {
  if (isMockMode()) return mockReturn(mockSavedProfile ?? sample.crop_profile)
  return request(`/crops/${encodeURIComponent(cropId)}`)
}

/**
 * Save the registration form. `form` has the CropProfileCreate fields:
 * farmer_name, preferred_language, crop_type, variety, sowing_date
 * ("YYYY-MM-DD"), area_acres (number), location_name, stage — and
 * optionally latitude + longitude (from getCurrentPosition below). Without
 * coordinates the backend looks up location_name; an unknown place gives
 * ApiError status 422 with a helpful message to show the farmer.
 *
 * - With `cropId`: EDITS that crop (PUT) — same crop_id, history kept.
 * - Without `cropId`: REGISTERS a new farmer + crop (POST) — returns a new
 *   crop_id; pass it to `onCropChange` so the rest of the app uses it.
 * Returns the full CropProfile.
 */
export async function saveCropProfile(form, cropId = null) {
  if (isMockMode()) {
    const sown = new Date(`${form.sowing_date}T00:00:00`)
    const days = Math.max(0, Math.floor((Date.now() - sown.getTime()) / 86_400_000))
    mockSavedProfile = {
      ...sample.crop_profile, // keeps the demo crop_id and coordinates
      farmer_name: form.farmer_name,
      preferred_language: form.preferred_language ?? 'en',
      crop_type: form.crop_type,
      variety: form.variety || null,
      sowing_date: form.sowing_date,
      days_since_sowing: days,
      area_acres: Number(form.area_acres),
      location: { ...sample.crop_profile.location, name: form.location_name },
      stage: form.stage,
      expected_harvest_start: null,
      expected_harvest_end: null,
      yield_estimate: null,
    }
    return mockReturn(mockSavedProfile)
  }
  if (cropId) {
    return request(`/crops/${encodeURIComponent(cropId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
  }
  return postJSON('/crops', form)
}

/**
 * Real recent + forecast weather at the crop's location (Open-Meteo).
 * Shape: {source, rain_last_3_days_mm, avg_humidity_pct, avg_temp_c,
 * rain_next_3_days_mm, max_rain_chance_next_3_days_pct, summary}.
 * Throws ApiError 503 if the weather service is unreachable.
 */
export async function getWeather(cropId) {
  if (isMockMode()) return mockReturn(sample.analysis.weather)
  return request(`/crops/${encodeURIComponent(cropId)}/weather`)
}

/**
 * Ask the browser for the phone/laptop's GPS position (the user must allow
 * it). Resolves to {latitude, longitude}; rejects with an Error if denied
 * or unavailable. Pass the result along with the form to saveCropProfile.
 */
export function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error('Location is not available on this device.'))
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({
        latitude: Number(pos.coords.latitude.toFixed(5)),
        longitude: Number(pos.coords.longitude.toFixed(5)),
      }),
      (err) => reject(new Error(err.message || 'Location permission was denied.')),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 },
    )
  })
}

// ---------------------------------------------------------------------------
// F1 + F3 + F2 + F4 — leaf analysis (Teammate 2)
// ---------------------------------------------------------------------------

/**
 * Upload a leaf photo (`file` from an <input type="file">) and get back an
 * AnalysisResult. Mock mode ignores the photo and returns the sample result
 * (is_demo: true, so the screen shows the DEMO EXAMPLE tag).
 */
export async function analyzeImage(cropId, file) {
  if (isMockMode()) return mockReturn(sample.analysis)
  const form = new FormData()
  form.append('image', file)
  return request(`/crops/${encodeURIComponent(cropId)}/analyze`, { method: 'POST', body: form })
}

/** Newest analysis for the crop, or null if there isn't one yet. */
export async function getLatestAnalysis(cropId) {
  const history = await getHistory(cropId)
  return history[0] ?? null
}

/** All analyses for the crop, newest first (powers "track progress"). */
export async function getHistory(cropId) {
  if (isMockMode()) return mockReturn([sample.analysis])
  return request(`/crops/${encodeURIComponent(cropId)}/history`)
}

// ---------------------------------------------------------------------------
// F5 — finance & loans, MOCK DATA (Teammate 3)
// ---------------------------------------------------------------------------

// Mock mode keeps document ticks here (lost on page reload).
let mockLoan = null

/** Throws ApiError with status 404 when the farmer has no loan records yet. */
export async function getLoanSummary(cropId) {
  if (isMockMode()) return mockReturn(mockLoan ?? sample.loan_summary)
  return request(`/crops/${encodeURIComponent(cropId)}/loan`)
}

/** Tick / untick a checklist document. Returns the updated LoanSummary. */
export async function setDocumentSubmitted(cropId, code, submitted) {
  if (isMockMode()) {
    const loan = structuredClone(mockLoan ?? sample.loan_summary)
    loan.documents = loan.documents.map((d) => (d.code === code ? { ...d, submitted } : d))
    loan.missing_document_codes = loan.documents.filter((d) => !d.submitted).map((d) => d.code)
    mockLoan = loan
    return mockReturn(loan)
  }
  return request(`/crops/${encodeURIComponent(cropId)}/loan/documents/${encodeURIComponent(code)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ submitted }),
  })
}

// ---------------------------------------------------------------------------
// F7 — chatbot (Teammate 4)
// ---------------------------------------------------------------------------

// Keyword routing so the chat feels alive in mock mode (same rules as the
// backend skeleton). Safety questions are checked first.
const MOCK_CHAT_KEYWORDS = [
  [['pesticide', 'spray', 'dose', 'दवा', 'कीटनाशक', 'छिड़काव'], 2],
  [['कागज', 'कागज़', 'दस्तावेज', 'document', 'loan', 'लोन'], 0],
  [['why', 'क्यों', 'inspect', 'जाँच'], 1],
]
const MOCK_UNKNOWN_REPLY = {
  en: "(Demo mode) I'll be able to answer this once the chatbot is connected.",
  hi: '(डेमो मोड) चैटबॉट जुड़ने के बाद मैं इसका जवाब दे पाऊँगा।',
}

/**
 * Send a chat message. `history` = earlier turns, oldest first:
 * [{role: 'user' | 'assistant', text}]. Returns a ChatReply:
 * {reply, lang, used_context, is_fallback}.
 */
export async function sendChat(cropId, message, lang, history = []) {
  if (isMockMode()) {
    const text = message.toLowerCase()
    for (const [words, index] of MOCK_CHAT_KEYWORDS) {
      if (words.some((w) => text.includes(w))) return mockReturn(sample.chat_examples[index].reply)
    }
    return mockReturn({
      reply: MOCK_UNKNOWN_REPLY[lang] ?? MOCK_UNKNOWN_REPLY.en,
      lang,
      used_context: [],
      is_fallback: true,
    })
  }
  return postJSON('/chat', { crop_id: cropId, message, lang, history: history.slice(-20) })
}

/**
 * Speech-to-text for the voice assistant: send a recorded Blob, get back
 * {text, lang}. Throws ApiError 503 if voice input is unavailable.
 */
export async function transcribeAudio(blob, lang) {
  if (isMockMode()) {
    return mockReturn({ text: lang === 'hi' ? 'लोन के लिए कौन से कागज़ बाकी हैं?' : 'Why should I inspect nearby plants?', lang })
  }
  const form = new FormData()
  const ext = blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'
  form.append('audio', blob, `question.${ext}`)
  form.append('lang', lang)
  return request('/voice/transcribe', { method: 'POST', body: form })
}
