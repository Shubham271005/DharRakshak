/*
 * SCREEN: Leaf check — upload + analysis results (F1, F3, F2, F4)
 * OWNER:  Teammate 2
 * DATA:   analyzeImage(cropId, file)   -> AnalysisResult
 *         getLatestAnalysis(cropId)    -> AnalysisResult | null
 *         Fields: docs/CONTRACT.md, row "Analysis results"
 *
 * ========================================================================
 * YOUR TASK — step by step (delete each TODO once it's done)
 * ========================================================================
 * Run the app:  cd frontend && npm run dev   → http://localhost:5173
 *
 * TODO 1  Upload. Add <input type="file" accept="image/jpeg,image/png,image/webp">.
 *         Keep the chosen file in state and show a preview with
 *         <img src={URL.createObjectURL(file)} className="h-48 rounded-xl object-cover">.
 *         An "Analyze" button calls `await analyzeImage(cropId, file)` and
 *         stores the result in state (show <Loading /> while waiting,
 *         <ErrorBox> on failure — e.g. a .txt file gives a 415 in api mode).
 *         Until the farmer uploads, show the result from useApiData below.
 *
 * TODO 2  Tags next to the title (pass them as children of <ScreenHeader>):
 *         result.is_demo → <MockTag labelKey="demo_example" />
 *         result.weather?.source === 'mock' → <MockTag />
 *
 * TODO 3  Uncertain result. If result.uncertain, show a gold warning box
 *         with tr(result.uncertainty_message) ABOVE the predictions.
 *         If result.crop_mismatch, warn that the photo may show a
 *         different crop than the profile.
 *
 * TODO 4  Predictions (F1). For each p in result.predictions:
 *         tr(p.display_name), formatPercent(p.confidence), and a bar:
 *           <div className="h-2 rounded-full bg-tint">
 *             <div className="h-2 rounded-full bg-moss" style={{ width: formatPercent(p.confidence) }} />
 *           </div>
 *         First bar bg-moss, others bg-leaf. Never write "confirmed".
 *
 * TODO 5  Risk (F3). <Pill> with the level, tone by level:
 *           low → "leaf", moderate → "gold", elevated → "rust"
 *         ALWAYS followed by t('estimate'). Below: each reason
 *         tr(r.text) as a list, and tr(result.weather.summary) if present.
 *
 * TODO 6  Action cards (F2). Sort by priority:
 *           [...result.action_cards].sort((a, b) => a.priority - b.priority)
 *         Show in "grid gap-4 md:grid-cols-3". Each card: a round number
 *         badge (priority 1 in bg-rust, others bg-gold), tr(title) bold,
 *         tr(detail), and a <details><summary>Why?</summary>tr(why)</details>.
 *
 * TODO 7  Explanation (F4). A bg-tint rounded box with
 *         tr(result.explanation.summary) and, in bold,
 *         tr(result.explanation.verify).
 *
 * DONE WHEN
 *   [ ] The demo result matches the slide 4 mockup (3 bars, ELEVATED +
 *       "estimate", 3 action cards, Why box).
 *   [ ] DEMO EXAMPLE / MOCK DATA tags appear for sample data.
 *   [ ] Works on a phone-width window and in both languages.
 */
import { getLatestAnalysis } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { ErrorBox, Loading, RawData, ScreenHeader, StubBanner } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function AnalysisScreen({ cropId }) {
  const { t } = useLanguage()
  const { data: result, loading, error, reload } = useApiData(() => getLatestAnalysis(cropId), [cropId])

  return (
    <section>
      <ScreenHeader title={t('nav_analysis')} />
      <StubBanner owner="Teammate 2" />
      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {!loading && !error && <RawData data={result} />}
    </section>
  )
}
