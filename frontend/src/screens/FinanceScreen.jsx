/*
 * SCREEN: Loans & documents (F5) — MOCK DATA ONLY, no bank integration
 * OWNER:  Teammate 3
 * DATA:   getLoanSummary, setDocumentSubmitted
 *
 * POLISH TASKS for Teammate 3:
 *   [ ] Check scheme summaries (shared/content/schemes.json) against the official sites.
 *   [ ] Add a "days until next repayment" countdown.
 *   [ ] Demo prep: tick "Land record copy" live and show the progress bar move.
 */
import { BadgeIndianRupee, Banknote, CalendarClock, CheckCircle2, CircleAlert, ExternalLink, FileCheck2, Info, Landmark } from 'lucide-react'
import { useState } from 'react'
import { getLoanSummary, setDocumentSubmitted } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Card, ErrorBox, Loading, MockTag, Notice, Pill, ProgressBar, ScreenHeader, Stat } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate, formatINR } from '../lib/format.js'

const STATUS_TONES = { active: 'moss', overdue: 'rust', applied: 'gold', closed: 'muted' }

function LoanCard({ summary }) {
  const { lang, t, tr } = useLanguage()
  const { loan } = summary
  return (
    <Card title={tr(loan.display_name)} icon={Landmark}
      action={<Pill tone={STATUS_TONES[loan.status] ?? 'muted'}>{t(`loan_status_${loan.status}`)}</Pill>}>
      <div className="grid gap-2 sm:grid-cols-3">
        <Stat icon={BadgeIndianRupee} label={t('sanctioned')} value={formatINR(loan.sanctioned_amount_inr)} />
        <Stat icon={Banknote} label={t('outstanding')} value={formatINR(loan.outstanding_amount_inr)} />
        <Stat icon={CalendarClock} label={t('next_repayment')}
          value={loan.next_repayment ? formatINR(loan.next_repayment.amount_inr) : '—'}
          sub={loan.next_repayment ? formatDate(loan.next_repayment.due_date, lang) : null} />
      </div>
      <p className="mt-2 text-[11px] text-muted">{t('lender')}: {loan.lender_name}</p>
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
    <Card title={t('documents_title')} icon={FileCheck2}>
      <div className="mb-1.5 flex justify-between text-sm">
        <span className="font-semibold text-forest">{t('documents_progress').replace('{done}', done).replace('{total}', total)}</span>
        <span className="text-xs text-muted">{Math.round((done / total) * 100)}%</span>
      </div>
      <ProgressBar value={done / total} label={t('documents_title')} />
      <ul className="mt-3 space-y-1">
        {documents.map((doc) => (
          <li key={doc.code}>
            <label className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg px-2 py-1.5 transition hover:bg-cream ${doc.submitted ? '' : 'bg-rust/5'}`}>
              <span className="flex items-center gap-2.5">
                <input type="checkbox" className="h-4 w-4 accent-moss" checked={doc.submitted}
                  disabled={busyCode === doc.code} onChange={() => toggle(doc)} />
                <span className={`text-sm ${doc.submitted ? 'text-ink' : 'font-semibold text-rust'}`}>{tr(doc.name)}</span>
              </span>
              {doc.submitted
                ? <span className="flex items-center gap-1 text-[11px] text-moss"><CheckCircle2 className="h-3.5 w-3.5" />{t('submitted')}</span>
                : <span className="flex items-center gap-1 text-[11px] text-rust"><CircleAlert className="h-3.5 w-3.5" />{t('missing')}</span>}
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">{t('documents_note')}</p>
      {error && <div className="mt-2"><ErrorBox error={error} /></div>}
    </Card>
  )
}

function SchemesCard({ schemes }) {
  const { t, tr } = useLanguage()
  return (
    <Card title={t('schemes_title')} icon={Info}>
      <ul className="space-y-3">
        {schemes.map((s) => (
          <li key={s.code} className="rounded-xl bg-cream/60 p-3">
            <p className="text-sm font-semibold text-forest">{tr(s.name)}</p>
            <p className="mt-0.5 text-sm leading-snug">{tr(s.summary)}</p>
            <p className="mt-1 text-xs italic text-muted">{tr(s.verify_note)}</p>
            {s.official_url && (
              <a href={s.official_url} target="_blank" rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-moss underline-offset-2 hover:underline">
                {s.official_url.replace('https://', '')} <ExternalLink className="h-3 w-3" />
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
    <section className="space-y-4">
      <ScreenHeader title={t('nav_finance')} subtitle={t('finance_subtitle')}>
        {summary?.data_source === 'mock' && <MockTag />}
      </ScreenHeader>
      {summary?.data_source === 'mock' && <Notice tone="gold" icon={Info}>{t('mock_loan_note')}</Notice>}
      {loading && !summary && <Loading />}
      {error?.status === 404
        ? <Card><p className="text-sm text-forest">{t('no_loan_yet')}</p></Card>
        : error && <ErrorBox error={error} onRetry={reload} />}
      {summary && (
        <>
          <LoanCard summary={summary} />
          <div className="grid gap-4 lg:grid-cols-2">
            <DocumentsCard summary={summary} cropId={cropId} onUpdate={setUpdated} />
            <SchemesCard schemes={summary.schemes} />
          </div>
        </>
      )}
    </section>
  )
}
