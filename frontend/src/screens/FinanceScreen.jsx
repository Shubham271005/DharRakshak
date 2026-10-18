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
import { BadgeIndianRupee, Banknote, CalendarClock, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Clock, ExternalLink, FileCheck2, History, Info, Landmark, Percent, ShieldCheck } from 'lucide-react'
import { useRef, useState } from 'react'
import pmfbyImg from '../assets/schemes/pmfby.svg'
import pmkisanImg from '../assets/schemes/pmkisan.svg'
import { BANKS, PAST_LOANS } from '../data/banks.js'
import { getLoanSummary, setDocumentSubmitted } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { Card, ErrorBox, Loading, MockTag, Notice, Pill, ProgressBar, ScreenHeader, Stat } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { formatDate, formatINR } from '../lib/format.js'

const STATUS_TONES = { active: 'moss', overdue: 'rust', applied: 'gold', closed: 'muted' }

/** Horizontal, swipeable bank comparison (scroll-snap + arrow buttons). */
function BankSlider() {
  const { t, tr } = useLanguage()
  const track = useRef(null)
  const [index, setIndex] = useState(0)
  const go = (i) => {
    const el = track.current
    const next = Math.max(0, Math.min(BANKS.length - 1, i))
    el?.children[next]?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'start' })
    setIndex(next)
  }
  const onScroll = () => {
    const el = track.current
    if (!el) return
    const w = el.children[0]?.offsetWidth || 1
    setIndex(Math.round(el.scrollLeft / (w + 16)))
  }
  const arrow = 'flex h-8 w-8 items-center justify-center rounded-full bg-white shadow ring-1 ring-black/5 transition hover:bg-tint disabled:opacity-40'
  return (
    <Card title={t('bank_compare_title')} icon={Percent}
      action={<div className="flex gap-1.5">
        <button className={arrow} onClick={() => go(index - 1)} disabled={index === 0} aria-label="Previous"><ChevronLeft className="h-4 w-4" /></button>
        <button className={arrow} onClick={() => go(index + 1)} disabled={index >= BANKS.length - 1} aria-label="Next"><ChevronRight className="h-4 w-4" /></button>
      </div>}>
      <p className="mb-3 text-xs text-muted">{t('bank_compare_hint')}</p>
      <div ref={track} onScroll={onScroll}
        className="-mx-1 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-1 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {BANKS.map((b) => (
          <article key={b.id} className="group/card flex w-[85%] shrink-0 snap-start flex-col overflow-hidden rounded-2xl border border-black/5 bg-white shadow-sm transition hover:shadow-lg sm:w-[calc(50%-8px)] xl:w-[calc(33.333%-11px)]">
            <div className={`leaf-pattern bg-gradient-to-br ${b.tone} p-4 text-white`}>
              <div className="flex items-center gap-3">
                <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/20 text-sm font-extrabold ring-1 ring-white/30">{b.short}</span>
                <div className="min-w-0">
                  <p className="truncate font-bold">{b.name}</p>
                  <p className="text-xs text-white/80">KCC</p>
                </div>
              </div>
              <div className="mt-3 flex items-end gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-white/75">{t('interest_rate')}</p>
                  <p className="text-3xl font-extrabold leading-none">{b.rate.toFixed(1)}%<span className="text-sm font-semibold text-white/80"> {t('per_year')}</span></p>
                </div>
                <div className="rounded-lg bg-white/15 px-2 py-1 text-xs">
                  {t('effective_rate')}: <b>{b.effective.toFixed(1)}%</b>
                </div>
              </div>
            </div>
            <div className="flex flex-1 flex-col gap-3 p-4 text-sm">
              <dl className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-cream/70 p-2"><dt className="text-muted">{t('above_3_lakh')}</dt><dd className="font-bold text-forest">{b.above}</dd></div>
                <div className="rounded-lg bg-cream/70 p-2"><dt className="text-muted">{t('collateral_free')}</dt><dd className="font-bold text-forest">{formatINR(b.maxNoCollateral)}</dd></div>
                <div className="rounded-lg bg-cream/70 p-2"><dt className="text-muted">{t('processing_fee')}</dt><dd className="font-bold text-forest">{tr(b.fee)}</dd></div>
                <div className="rounded-lg bg-cream/70 p-2"><dt className="flex items-center gap-1 text-muted"><Clock className="h-3 w-3" />{t('approval_time')}</dt><dd className="font-bold text-forest">{b.days} {t('days_unit')}</dd></div>
              </dl>
              <div>
                <p className="mb-1.5 text-[11px] font-bold uppercase tracking-wide text-muted">{t('docs_required')}</p>
                <ul className="space-y-1">
                  {b.docs.map((d) => (
                    <li key={d.en} className="flex items-start gap-2 text-[13px]"><CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-moss" />{tr(d)}</li>
                  ))}
                </ul>
              </div>
            </div>
          </article>
        ))}
      </div>
      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="flex gap-1.5">
          {BANKS.map((b, i) => (
            <button key={b.id} onClick={() => go(i)} aria-label={b.name}
              className={`h-2 rounded-full transition-all ${i === index ? 'w-6 bg-moss' : 'w-2 bg-moss/25'}`} />
          ))}
        </div>
        <p className="text-[11px] text-muted">{t('indicative_note')}</p>
      </div>
    </Card>
  )
}

function PastLoansCard() {
  const { lang, t, tr } = useLanguage()
  return (
    <Card title={t('past_loans_title')} icon={History} action={<MockTag />}>
      <ol className="relative space-y-3 border-l-2 border-tint pl-5">
        {PAST_LOANS.map((l) => (
          <li key={l.id} className="relative">
            <span className={`absolute -left-[27px] top-1 h-3.5 w-3.5 rounded-full ring-4 ring-white ${l.onTime ? 'bg-moss' : 'bg-gold'}`} />
            <div className="rounded-xl border border-black/5 bg-gradient-to-b from-white to-cream/50 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-forest">{tr(l.name)}</p>
                <Pill tone={l.onTime ? 'moss' : 'gold'}>{l.onTime ? t('repaid_on_time') : t('repaid_late')}</Pill>
              </div>
              <p className="mt-0.5 text-xs text-muted">{l.bank} · {formatDate(l.from, lang)} – {formatDate(l.to, lang)}</p>
              <div className="mt-2 flex gap-4 text-sm">
                <span><b className="text-forest">{formatINR(l.amount)}</b></span>
                <span className="text-muted">{l.rate.toFixed(1)}% {t('per_year')}</span>
              </div>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

const SCHEME_IMAGES = [
  { img: pmkisanImg, title: 'pmkisan_title', caption: 'pmkisan_caption', url: 'https://pmkisan.gov.in' },
  { img: pmfbyImg, title: 'pmfby_title', caption: 'pmfby_caption', url: 'https://pmfby.gov.in' },
]

function SchemeGallery() {
  const { t } = useLanguage()
  return (
    <Card title={t('gov_schemes_title')} icon={ShieldCheck} className="lg:col-span-2" bodyClassName="grid gap-4 p-4 sm:grid-cols-2">
      {SCHEME_IMAGES.map((s) => (
        <a key={s.title} href={s.url} target="_blank" rel="noreferrer"
          className="group/card overflow-hidden rounded-2xl border border-black/5 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg">
          <div className="overflow-hidden">
            <img src={s.img} alt={t(s.title)} className="aspect-[2/1] w-full object-cover transition duration-500 group-hover/card:scale-105" />
          </div>
          <div className="p-3">
            <p className="font-bold text-forest">{t(s.title)}</p>
            <p className="mt-0.5 text-sm leading-snug text-muted">{t(s.caption)}</p>
            <p className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-moss">{t('visit_site')} <ExternalLink className="h-3 w-3" /></p>
          </div>
        </a>
      ))}
    </Card>
  )
}

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
            <PastLoansCard />
          </div>
          <BankSlider />
          <div className="grid gap-4 lg:grid-cols-3">
            <SchemeGallery />
            <SchemesCard schemes={summary.schemes} />
          </div>
        </>
      )}
    </section>
  )
}
