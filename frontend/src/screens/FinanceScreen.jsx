/*
 * SCREEN: Loans & documents (F5) — MOCK DATA ONLY, no bank integration
 * OWNER:  Teammate 3
 * DATA:   getLoanSummary, setDocumentSubmitted (docs/CONTRACT.md, "Finance & loans")
 *
 * This screen is fully working. POLISH TASKS for Teammate 3:
 *   [ ] Read the scheme summaries (shared/content/schemes.json) against the
 *       official websites and fix anything that's out of date.
 *   [ ] Add a "days until next repayment" countdown to the loan card.
 *   [ ] Check every label in हिंदी mode with a Hindi speaker.
 *   [ ] Demo prep: tick "Land record copy" live and show the progress bar move.
 */
import { useState } from 'react'
import { getLoanSummary, setDocumentSubmitted } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Card, ErrorBox, Loading, MockTag, Notice, Pill, ProgressBar, ScreenHeader, SectionTitle } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate, formatINR } from '../lib/format.js'

const STATUS_TONES = { active: 'moss', overdue: 'rust', applied: 'gold', closed: 'muted' }

function Metric({ label, value, sub }) {
  return (
    <div className="rounded-xl bg-cream p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-2xl font-bold text-forest">{value}</p>
      {sub && <p className="text-xs text-muted">{sub}</p>}
    </div>
  )
}

function LoanCard({ summary }) {
  const { lang, t, tr } = useLanguage()
  const { loan } = summary
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-bold text-forest">{tr(loan.display_name)}</h2>
        <Pill tone={STATUS_TONES[loan.status] ?? 'muted'}>{t(`loan_status_${loan.status}`)}</Pill>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label={t('sanctioned')} value={formatINR(loan.sanctioned_amount_inr)} />
        <Metric label={t('outstanding')} value={formatINR(loan.outstanding_amount_inr)} />
        <Metric
          label={t('next_repayment')}
          value={loan.next_repayment ? formatINR(loan.next_repayment.amount_inr) : '—'}
          sub={loan.next_repayment ? formatDate(loan.next_repayment.due_date, lang) : null}
        />
      </div>
      <p className="mt-3 text-xs text-muted">{t('lender')}: {loan.lender_name}</p>
    </Card>
  )
}

function DocumentsCard({ summary, cropId, onUpdate }) {
  const { t, tr } = useLanguage()
  const [busyCode, setBusyCode] = useState(null)
  const [pending, setPending] = useState({}) // optimistic ticks: {code: submitted}
  const [error, setError] = useState(null)
  // Show the farmer's tap immediately; the server reply confirms it.
  const documents = summary.documents.map((d) => (d.code in pending ? { ...d, submitted: pending[d.code] } : d))
  const done = documents.filter((d) => d.submitted).length
  const total = documents.length

  async function toggle(doc) {
    const next = !doc.submitted
    setBusyCode(doc.code)
    setPending((p) => ({ ...p, [doc.code]: next }))
    setError(null)
    try {
      onUpdate(await setDocumentSubmitted(cropId, doc.code, next))
    } catch (err) {
      setError(err) // roll back: the server didn't save it
    } finally {
      setPending((p) => {
        const { [doc.code]: _, ...rest } = p
        return rest
      })
      setBusyCode(null)
    }
  }

  return (
    <Card>
      <SectionTitle>{t('documents_title')}</SectionTitle>
      <div className="mb-2 flex justify-between text-sm">
        <span className="font-semibold text-forest">{t('documents_progress').replace('{done}', done).replace('{total}', total)}</span>
        <span className="text-muted">{Math.round((done / total) * 100)}%</span>
      </div>
      <ProgressBar value={done / total} label={t('documents_title')} />
      <ul className="mt-4 divide-y divide-tint">
        {documents.map((doc) => (
          <li key={doc.code} className="flex items-center justify-between gap-3 py-2.5">
            <label className="flex cursor-pointer items-center gap-3">
              <input
                type="checkbox"
                className="h-5 w-5 accent-moss"
                checked={doc.submitted}
                disabled={busyCode === doc.code}
                onChange={() => toggle(doc)}
              />
              <span className={doc.submitted ? 'text-ink' : 'font-semibold text-rust'}>{tr(doc.name)}</span>
            </label>
            <span className="text-xs">{doc.submitted ? `✅ ${t('submitted')}` : `❌ ${t('missing')}`}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">{t('documents_note')}</p>
      {error && <div className="mt-3"><ErrorBox error={error} /></div>}
    </Card>
  )
}

function SchemesCard({ schemes }) {
  const { t, tr } = useLanguage()
  return (
    <Card>
      <SectionTitle>{t('schemes_title')}</SectionTitle>
      <ul className="space-y-4">
        {schemes.map((s) => (
          <li key={s.code}>
            <p className="font-bold text-forest">{tr(s.name)}</p>
            <p className="text-sm">{tr(s.summary)}</p>
            <p className="text-sm italic text-muted">{tr(s.verify_note)}</p>
            {s.official_url && (
              <a href={s.official_url} target="_blank" rel="noreferrer" className="text-sm font-semibold text-moss underline">
                {s.official_url.replace('https://', '')} ↗
              </a>
            )}
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function FinanceScreen({ cropId }) {
  const { t } = useLanguage()
  const { data, loading, error, reload } = useApiData(() => getLoanSummary(cropId), [cropId])
  const [updated, setUpdated] = useState(null)
  const summary = updated?.crop_id === cropId ? updated : data

  return (
    <section className="space-y-6">
      <ScreenHeader title={t('nav_finance')} subtitle={t('finance_subtitle')}>
        {summary?.data_source === 'mock' && <MockTag />}
      </ScreenHeader>
      {summary?.data_source === 'mock' && <Notice tone="gold">{t('mock_loan_note')}</Notice>}
      {loading && !summary && <Loading />}
      {error?.status === 404 ? (
        <Card><p className="text-forest">🗂 {t('no_loan_yet')}</p></Card>
      ) : (
        error && <ErrorBox error={error} onRetry={reload} />
      )}
      {summary && (
        <>
          <LoanCard summary={summary} />
          <div className="grid gap-6 lg:grid-cols-2">
            <DocumentsCard summary={summary} cropId={cropId} onUpdate={setUpdated} />
            <SchemesCard schemes={summary.schemes} />
          </div>
        </>
      )}
    </section>
  )
}
