/*
 * SCREEN: Ask DharRakshak — multilingual chatbot + voice assistant (F7, F6)
 * OWNER:  Teammate 4
 * DATA:   sendChat, transcribeAudio (docs/CONTRACT.md, "Chatbot + language")
 *         Voice: lib/speech.js (mic recording + browser read-aloud)
 *
 * How voice works: tap 🎤 → speak → tap again. The recording goes to
 * /api/voice/transcribe (Groq Whisper), the text is sent as a normal chat
 * message, and the answer is read aloud with the browser's voice.
 *
 * This screen is fully working. POLISH TASKS for Teammate 4:
 *   [ ] Test the mic in Chrome on a laptop AND a phone; note any issues.
 *   [ ] Check whether your devices have a Hindi voice (Chrome on Android
 *       usually does). If not, the speaker button explains why.
 *   [ ] Add a "copy answer" button on assistant messages.
 *   [ ] Make all four screens look consistent (spacing, card styles).
 *   [ ] Check every label in हिंदी mode with a Hindi speaker.
 */
import { useEffect, useRef, useState } from 'react'
import { sendChat, transcribeAudio } from '../api/client.js'
import { Button, Card, ErrorBox, Notice, ScreenHeader } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'
import { useSessionState } from '../lib/useSessionState.js'
import { useRecorder, useSpeaker } from '../lib/speech.js'

const SUGGESTIONS = {
  hi: ['लोन के लिए कौन से कागज़ बाकी हैं?', 'मेरी फसल को अभी क्या खतरा है?', 'मुझे आज क्या करना चाहिए?'],
  en: ['Which loan documents are still missing?', 'Why should I inspect nearby plants?', 'What should I do this week?'],
}

function Bubble({ turn }) {
  const { t } = useLanguage()
  const mine = turn.role === 'user'
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${mine ? 'rounded-br-sm bg-moss text-white' : 'rounded-bl-sm border border-tint bg-white text-ink'}`}>
        {turn.viaVoice && <span className="mr-1" title={t('sent_by_voice')}>🎤</span>}
        {turn.text}
        {turn.isFallback && <p className="mt-1 text-xs italic text-muted">{t('fallback_note')}</p>}
      </div>
    </div>
  )
}

export default function ChatScreen({ cropId }) {
  const { lang, t } = useLanguage()
  const [history, setHistory] = useSessionState(`chat.${cropId}`, [])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false) // waiting for an answer or a transcript
  const [error, setError] = useState(null)
  const [micNote, setMicNote] = useState(null) // gentle voice messages, in the farmer's language
  const [speakReplies, setSpeakReplies] = useSessionState('chat.speak', true)
  const recorder = useRecorder()
  const speaker = useSpeaker()
  const listRef = useRef(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' })
  }, [history, busy])
  // Stop talking when leaving the screen. Depend on the stable `stop`
  // function, not the `speaker` object (a new object every render would
  // cut off every reply the moment it starts).
  const stopSpeaking = speaker.stop
  useEffect(() => () => stopSpeaking(), [stopSpeaking])

  async function ask(text, viaVoice = false) {
    const question = text.trim()
    if (!question || busy) return
    setError(null)
    const before = history
    setHistory([...before, { role: 'user', text: question, viaVoice }])
    setInput('')
    setBusy(true)
    try {
      const reply = await sendChat(cropId, question, lang, before.map(({ role, text: t2 }) => ({ role, text: t2 })))
      setHistory((h) => [...h, { role: 'assistant', text: reply.reply, isFallback: reply.is_fallback }])
      if (speakReplies) speaker.speak(reply.reply, reply.lang)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  async function toggleMic() {
    setError(null)
    setMicNote(null)
    if (!recorder.recording) {
      speaker.stop()
      try {
        await recorder.start()
      } catch {
        setError(new Error(t('mic_blocked')))
      }
      return
    }
    const blob = await recorder.stop()
    if (!blob || blob.size === 0) return
    setBusy(true)
    try {
      const { text } = await transcribeAudio(blob, lang)
      setBusy(false)
      await ask(text, true)
    } catch (err) {
      // 422 = no speech heard, 503 = voice service down: say it kindly.
      if (err.status === 422) setMicNote(t('no_speech_heard'))
      else if (err.status === 503) setMicNote(t('voice_unavailable'))
      else setError(err)
      setBusy(false)
    }
  }

  const canSpeakNow = speaker.canSpeak(lang)

  return (
    <section className="space-y-4">
      <ScreenHeader title={t('nav_chat')} subtitle={t('chat_subtitle')}>
        <Button
          variant="ghost"
          onClick={() => { setSpeakReplies(!speakReplies); speaker.stop() }}
          disabled={!canSpeakNow}
          title={canSpeakNow ? '' : t('no_voice_for_language')}
        >
          {speakReplies && canSpeakNow ? '🔊' : '🔇'} {t(speakReplies && canSpeakNow ? 'voice_on' : 'voice_off')}
        </Button>
        {history.length > 0 && <Button variant="ghost" onClick={() => { setHistory([]); speaker.stop() }}>{t('clear_chat')}</Button>}
      </ScreenHeader>

      {!canSpeakNow && lang !== 'en' && <Notice tone="tint">{t('no_voice_for_language')}</Notice>}

      <Card className="p-0">
        <div ref={listRef} className="h-[26rem] space-y-3 overflow-y-auto p-4" aria-live="polite">
          {history.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
              <p className="text-4xl">🌱</p>
              <p className="max-w-md text-sm text-muted">{t('chat_empty')}</p>
            </div>
          )}
          {history.map((turn, i) => <Bubble key={i} turn={turn} />)}
          {busy && <p className="text-sm text-muted">{recorder.recording ? '' : t('thinking')}</p>}
        </div>

        <div className="flex flex-wrap gap-2 border-t border-tint px-4 pt-3">
          {SUGGESTIONS[lang].map((q) => (
            <button key={q} onClick={() => ask(q)} disabled={busy} className="rounded-full bg-tint px-3 py-1 text-xs font-semibold text-moss hover:bg-leaf/30 disabled:opacity-50">
              {q}
            </button>
          ))}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); ask(input) }} className="flex items-center gap-2 p-4">
          {recorder.supported && (
            <button
              type="button"
              onClick={toggleMic}
              disabled={busy && !recorder.recording}
              aria-pressed={recorder.recording}
              aria-label={recorder.recording ? t('stop_recording') : t('start_recording')}
              className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-lg transition ${recorder.recording ? 'animate-pulse bg-rust text-white' : 'bg-tint hover:bg-leaf/30'}`}
            >
              {recorder.recording ? '■' : '🎤'}
            </button>
          )}
          <input
            className="w-full rounded-full border border-tint bg-cream px-4 py-2.5 outline-none focus:border-moss"
            value={recorder.recording ? t('listening') : input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('chat_placeholder')}
            disabled={busy || recorder.recording}
            maxLength={1000}
          />
          <Button type="submit" disabled={busy || recorder.recording || !input.trim()}>{t('send')}</Button>
        </form>
      </Card>

      {micNote && <Notice tone="gold">🎤 {micNote}</Notice>}
      {error && <ErrorBox error={error} />}
      <p className="text-xs text-muted">{t('chat_disclaimer')}</p>
    </section>
  )
}
