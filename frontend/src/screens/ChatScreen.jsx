/*
 * SCREEN: Ask DharRakshak — multilingual chatbot + push-to-talk voice (F7, F6)
 * OWNER:  Teammate 4
 * DATA:   sendChat, transcribeAudio. Voice helpers: lib/speech.js
 *
 * Voice: tap 🎤, speak, tap ■. The recording goes to /api/voice/transcribe
 * (Groq Whisper: English, Hindi, Marathi, Punjabi; Haryanvi and Bhojpuri use
 * Hindi, the closest language Whisper knows), the text is sent as a chat
 * message, and the reply is read aloud with the device's voice for the
 * selected language when one is installed.
 *
 * POLISH TASKS for Teammate 4:
 *   [ ] Test the mic in Chrome on a laptop AND a phone, in Hindi and Marathi.
 *   [ ] Note which languages have a read-aloud voice on your demo devices.
 *   [ ] Add a "copy answer" button on assistant messages.
 */
import { Bot, Mic, Send, Square, Trash2, Volume2, VolumeX } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { sendChat, transcribeAudio } from '../api/client.js'
import { Button, ErrorBox, Notice, ScreenHeader } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { useRecorder, useSpeaker } from '../lib/speech.js'
import { useSessionState } from '../lib/useSessionState.js'

const SUGGESTION_KEYS = ['quick_q_documents', 'quick_q_risk', 'quick_q_today']

function Bubble({ turn }) {
  const { t } = useLanguage()
  const mine = turn.role === 'user'
  return (
    <div className={`flex items-end gap-2 ${mine ? 'justify-end' : 'justify-start'}`}>
      {!mine && (
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-tint text-moss">
          <Bot className="h-4 w-4" aria-hidden />
        </span>
      )}
      <div className={`max-w-[80%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${mine ? 'rounded-br-md bg-moss text-white' : 'rounded-bl-md bg-cream text-ink'}`}>
        {turn.viaVoice && <Mic className="mr-1 inline h-3.5 w-3.5 align-[-2px] opacity-80" aria-label={t('sent_by_voice')} />}
        {turn.text}
        {turn.isFallback && <p className="mt-1 text-[11px] italic text-muted">{t('fallback_note')}</p>}
      </div>
    </div>
  )
}

export default function ChatScreen({ cropId }) {
  const { lang, t, speechLang, sttLang } = useLanguage()
  const [history, setHistory] = useSessionState(`chat.${cropId}`, [])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [micNote, setMicNote] = useState(null)
  const [speakReplies, setSpeakReplies] = useSessionState('chat.speak', true)
  const recorder = useRecorder()
  const speaker = useSpeaker()
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [history, busy])
  // Stop talking when leaving the screen (depend on the stable `stop`, not the object).
  const stopSpeaking = speaker.stop
  useEffect(() => () => stopSpeaking(), [stopSpeaking])

  async function ask(text, viaVoice = false) {
    const question = text.trim()
    if (!question || busy) return
    setError(null)
    setMicNote(null)
    const before = history
    setHistory([...before, { role: 'user', text: question, viaVoice }])
    setInput('')
    setBusy(true)
    try {
      const reply = await sendChat(cropId, question, lang, before.map(({ role, text: x }) => ({ role, text: x })))
      setHistory((h) => [...h, { role: 'assistant', text: reply.reply, isFallback: reply.is_fallback }])
      if (speakReplies) speaker.speak(reply.reply, speechLang)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  // A question picked on the dashboard arrives through sessionStorage.
  useEffect(() => {
    let pending = null
    try {
      pending = sessionStorage.getItem('chat.pending')
      sessionStorage.removeItem('chat.pending')
    } catch {
      /* ignore */
    }
    if (pending) ask(pending)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function toggleMic() {
    setError(null)
    setMicNote(null)
    if (!recorder.recording) {
      speaker.stop()
      try {
        await recorder.start()
      } catch {
        setMicNote(t('mic_blocked'))
      }
      return
    }
    const blob = await recorder.stop()
    if (!blob || blob.size === 0) return
    setBusy(true)
    try {
      const { text } = await transcribeAudio(blob, sttLang)
      setBusy(false)
      await ask(text, true)
    } catch (err) {
      if (err.status === 422) setMicNote(t('no_speech_heard'))
      else if (err.status === 503) setMicNote(t('voice_unavailable'))
      else setError(err)
      setBusy(false)
    }
  }

  const canSpeakNow = speaker.canSpeak(speechLang)

  return (
    <section className="flex flex-col">
      <ScreenHeader title={t('nav_chat')} subtitle={t('chat_subtitle')}>
        <Button variant="ghost" icon={speakReplies && canSpeakNow ? Volume2 : VolumeX}
          onClick={() => { setSpeakReplies(!speakReplies); speaker.stop() }}
          disabled={!canSpeakNow} title={canSpeakNow ? '' : t('no_voice_for_language')}>
          <span className="hidden sm:inline">{t(speakReplies && canSpeakNow ? 'voice_on' : 'voice_off')}</span>
        </Button>
        {history.length > 0 && (
          <Button variant="ghost" icon={Trash2} onClick={() => { setHistory([]); speaker.stop() }}>
            <span className="hidden sm:inline">{t('clear_chat')}</span>
          </Button>
        )}
      </ScreenHeader>

      {!canSpeakNow && lang !== 'en' && <Notice tone="tint" className="mb-3">{t('no_voice_for_language')}</Notice>}

      <div className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-black/5 bg-white shadow-[0_1px_2px_rgba(16,40,24,0.06)]">
        <div ref={listRef} className="h-[calc(100dvh-22rem)] min-h-[16rem] space-y-3 overflow-y-auto p-4 md:h-[calc(100dvh-19rem)]" aria-live="polite">
          {history.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-tint text-moss"><Bot className="h-6 w-6" /></span>
              <p className="max-w-sm text-sm text-muted">{t('chat_empty')}</p>
            </div>
          )}
          {history.map((turn, i) => <Bubble key={i} turn={turn} />)}
          {busy && !recorder.recording && (
            <div className="flex items-center gap-2 text-xs text-muted">
              <span className="flex gap-1">{[0, 1, 2].map((i) => <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-moss/60" style={{ animationDelay: `${i * 120}ms` }} />)}</span>
              {t('thinking')}
            </div>
          )}
        </div>

        <div className="flex gap-2 overflow-x-auto border-t border-tint px-3 pt-2.5">
          {SUGGESTION_KEYS.map((key) => (
            <button key={key} onClick={() => ask(t(key))} disabled={busy}
              className="shrink-0 rounded-full bg-tint/70 px-3 py-1 text-xs font-medium text-forest transition hover:bg-tint disabled:opacity-50">
              {t(key)}
            </button>
          ))}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); ask(input) }} className="flex items-center gap-2 p-3">
          {recorder.supported && (
            <button type="button" onClick={toggleMic} disabled={busy && !recorder.recording} aria-pressed={recorder.recording}
              aria-label={recorder.recording ? t('stop_recording') : t('start_recording')}
              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition ${recorder.recording ? 'animate-pulse bg-rust text-white' : 'bg-tint text-moss hover:bg-leaf/30'}`}>
              {recorder.recording ? <Square className="h-4 w-4" /> : <Mic className="h-5 w-5" />}
            </button>
          )}
          <input
            className="min-w-0 flex-1 rounded-full border border-black/10 bg-cream/60 px-4 py-2 text-sm outline-none focus:border-moss focus:bg-white"
            value={recorder.recording ? t('listening') : input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('chat_placeholder')}
            disabled={busy || recorder.recording}
            maxLength={1000}
          />
          <Button type="submit" icon={Send} disabled={busy || recorder.recording || !input.trim()} aria-label={t('send')}>
            <span className="hidden sm:inline">{t('send')}</span>
          </Button>
        </form>
      </div>

      {micNote && <Notice tone="gold" icon={Mic} className="mt-3">{micNote}</Notice>}
      {error && <div className="mt-3"><ErrorBox error={error} /></div>}
      <p className="mt-2 text-[11px] text-muted">{t('chat_disclaimer')}</p>
    </section>
  )
}
