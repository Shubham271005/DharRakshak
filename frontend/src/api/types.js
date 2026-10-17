/*
 * JSDoc type hints that mirror shared/contract.py.
 *
 * Nothing here runs — it only gives VS Code autocomplete. To use it in a
 * screen, write a comment above a variable:
 *   /** @type {import('../api/types.js').LoanSummary} *\/
 *
 * If shared/contract.py changes, update the matching typedef here.
 */

/** @typedef {{en: string, hi: string, [lang: string]: string}} LocalizedText */

/**
 * @typedef {object} CropProfile
 * @property {string} crop_id
 * @property {string} farmer_name
 * @property {string} preferred_language
 * @property {string} crop_type
 * @property {string|null} variety
 * @property {string} sowing_date            "YYYY-MM-DD"
 * @property {number} days_since_sowing
 * @property {number} area_acres
 * @property {{name: string, latitude: number, longitude: number}} location
 * @property {'seedling'|'vegetative'|'flowering'|'fruiting'|'maturity'} stage
 * @property {string|null} expected_harvest_start
 * @property {string|null} expected_harvest_end
 * @property {{min_kg: number, max_kg: number}|null} yield_estimate   null = "range pending"
 */

/** @typedef {{label: string, display_name: LocalizedText, confidence: number}} Prediction */
/** @typedef {{code: string, points: number, text: LocalizedText}} RiskReason */
/** @typedef {{card_id: string, priority: number, title: LocalizedText, detail: LocalizedText, why: LocalizedText}} ActionCard */

/**
 * @typedef {object} AnalysisResult
 * @property {string} analysis_id
 * @property {string} crop_id
 * @property {string} created_at
 * @property {boolean} is_demo                       true = show DEMO EXAMPLE tag
 * @property {Prediction[]} predictions             1–3 items, highest confidence first
 * @property {boolean} uncertain
 * @property {LocalizedText|null} uncertainty_message
 * @property {boolean} crop_mismatch
 * @property {{source: 'open_meteo'|'mock', rain_last_3_days_mm: number, avg_humidity_pct: number, avg_temp_c: number, summary: LocalizedText}|null} weather
 * @property {{level: 'low'|'moderate'|'elevated', score: number, is_estimate: true, reasons: RiskReason[]}} risk
 * @property {ActionCard[]} action_cards
 * @property {{summary: LocalizedText, verify: LocalizedText}} explanation
 */

/**
 * @typedef {object} LoanSummary
 * @property {'mock'|'farmer_entered'} data_source
 * @property {string} crop_id
 * @property {{loan_id: string, loan_type: string, display_name: LocalizedText, lender_name: string, status: 'applied'|'active'|'overdue'|'closed', sanctioned_amount_inr: number, outstanding_amount_inr: number, next_repayment: {due_date: string, amount_inr: number}|null}} loan
 * @property {{code: string, name: LocalizedText, submitted: boolean}[]} documents
 * @property {string[]} missing_document_codes
 * @property {{code: string, name: LocalizedText, summary: LocalizedText, official_url: string|null, verify_note: LocalizedText}[]} schemes
 */

/** @typedef {{reply: string, lang: string, used_context: string[], is_fallback: boolean}} ChatReply */

export {}
