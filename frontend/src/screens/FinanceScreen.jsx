/*
 * SCREEN: Loans & documents (F5) — MOCK DATA ONLY, no bank integration
 * OWNER:  Teammate 3
 * DATA:   getLoanSummary(cropId) -> LoanSummary
 *         Fields: docs/CONTRACT.md, row "Finance & loans"
 *
 * ========================================================================
 * YOUR TASK — step by step (delete each TODO once it's done)
 * ========================================================================
 * Run the app:  cd frontend && npm run dev   → http://localhost:5173
 *
 * TODO 1  Mock label. If summary.data_source === 'mock', put <MockTag />
 *         in the <ScreenHeader> and a one-line note under it saying this
 *         is sample data, not connected to any bank (add the text to
 *         src/i18n/uiText.js in en + hi).
 *
 * TODO 2  Loan card. <Card> with tr(loan.display_name) as the heading and
 *         a <Pill> for loan.status:
 *           active → "moss", overdue → "rust", applied → "gold", closed → "muted"
 *         Then "grid gap-4 md:grid-cols-3" with three numbers:
 *         sanctioned, outstanding, next repayment (amount + formatDate).
 *         Money: formatINR(...). If next_repayment is null, show "—".
 *
 * TODO 3  Documents checklist. Count submitted:
 *           const done = summary.documents.filter((d) => d.submitted).length
 *         Show "3 of 5 submitted" and a progress bar (same style as the
 *         analysis bars, width = done / total * 100 + '%').
 *         One row per document: ✅ name when submitted; ❌ name in
 *         text-rust font-semibold when missing. Use tr(doc.name).
 *
 * TODO 4  Schemes. For each scheme: tr(name) in bold, tr(summary), and
 *         tr(verify_note) in italics (text-muted). If official_url exists,
 *         a link: <a href={url} target="_blank" rel="noreferrer">.
 *
 * TODO 5  Language: all labels via t(...); check in हिंदी.
 *
 * DONE WHEN
 *   [ ] Matches the finance panel on slide 4 (KCC sample, ₹48,000
 *       outstanding, ₹12,000 due 15 Dec, 3 of 5 documents).
 *   [ ] Land record + passport photo appear in red as missing.
 *   [ ] MOCK DATA tag is clearly visible.
 *   [ ] Works on a phone-width window and in both languages.
 */
import { getLoanSummary } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { ErrorBox, Loading, RawData, ScreenHeader, StubBanner } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function FinanceScreen({ cropId }) {
  const { t } = useLanguage()
  const { data: summary, loading, error, reload } = useApiData(() => getLoanSummary(cropId), [cropId])

  return (
    <section>
      <ScreenHeader title={t('nav_finance')} />
      <StubBanner owner="Teammate 3" />
      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {summary && <RawData data={summary} />}
    </section>
  )
}
