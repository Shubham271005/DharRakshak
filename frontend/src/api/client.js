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
 * ("YYYY-MM-DD"), area_acres (number), location_name, stage.
 * Returns the full CropProfile. In api mode the returned `crop_id` is NEW —
 * pass it to `onCropChange` so the rest of the app uses it.
 */
export async function saveCropProfile(form) {
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
  return postJSON('/crops', form)
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
  if (isMockMode()) return mockReturn(sample.analysis)
  const history = await request(`/crops/${encodeURIComponent(cropId)}/history`)
  return history[0] ?? null
}

// ---------------------------------------------------------------------------
// F5 — finance & loans, MOCK DATA (Teammate 3)
// ---------------------------------------------------------------------------

export async function getLoanSummary(cropId) {
  if (isMockMode()) return mockReturn(sample.loan_summary)
  return request(`/crops/${encodeURIComponent(cropId)}/loan`)
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

/** Send a chat message. Returns a ChatReply: {reply, lang, used_context, is_fallback}. */
export async function sendChat(cropId, message, lang) {
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
  return postJSON('/chat', { crop_id: cropId, message, lang })
}
