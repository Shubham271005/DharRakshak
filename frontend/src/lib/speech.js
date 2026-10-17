/*
 * Voice helpers for the chatbot (F7):
 *
 *   useRecorder()  — record a spoken question from the microphone.
 *   useSpeaker()   — read replies aloud with the browser's built-in voices
 *                    (free, no API key). Groq has no Hindi text-to-speech,
 *                    so the browser does this part.
 *
 * Microphone access needs a secure page: http://localhost is fine; a
 * deployed site must use https.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

const MAX_RECORDING_MS = 30_000 // a question rarely needs more than 30 s

/** First audio format this browser can record (Safari only does mp4). */
function pickMimeType() {
  const options = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4']
  return options.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) ?? ''
}

export function useRecorder() {
  const [recording, setRecording] = useState(false)
  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const resolveRef = useRef(null)
  const timerRef = useRef(null)

  const supported = typeof window !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && !!window.MediaRecorder

  /** Start recording. Rejects if the microphone is blocked or missing. */
  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mimeType = pickMimeType()
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    chunksRef.current = []
    recorder.ondataavailable = (e) => e.data.size > 0 && chunksRef.current.push(e.data)
    recorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop()) // turn the mic light off
      clearTimeout(timerRef.current)
      setRecording(false)
      resolveRef.current?.(new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' }))
    }
    recorderRef.current = recorder
    recorder.start()
    setRecording(true)
    timerRef.current = setTimeout(() => recorder.state === 'recording' && recorder.stop(), MAX_RECORDING_MS)
  }, [])

  /** Stop recording and get the audio Blob. */
  const stop = useCallback(
    () =>
      new Promise((resolve) => {
        resolveRef.current = resolve
        if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
        else resolve(null)
      }),
    [],
  )

  useEffect(() => () => recorderRef.current?.state === 'recording' && recorderRef.current.stop(), [])

  return { supported, recording, start, stop }
}

export function useSpeaker() {
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined
  const [voices, setVoices] = useState(() => synth?.getVoices() ?? [])

  // Voices load asynchronously in most browsers.
  useEffect(() => {
    if (!synth) return
    const update = () => setVoices(synth.getVoices())
    synth.addEventListener?.('voiceschanged', update)
    update()
    return () => synth.removeEventListener?.('voiceschanged', update)
  }, [synth])

  /** Best voice for a BCP-47 tag like 'mr-IN' (exact match, then same language). */
  const voiceFor = useCallback(
    (tag) => {
      const primary = tag.split('-')[0].toLowerCase()
      return voices.find((v) => v.lang === tag) ?? voices.find((v) => v.lang?.toLowerCase().startsWith(primary)) ?? null
    },
    [voices],
  )

  /** True if this device can read text aloud in `tag` (English always works). */
  const canSpeak = useCallback((tag) => !!synth && (tag.startsWith('en') || !!voiceFor(tag)), [synth, voiceFor])

  const speak = useCallback(
    (text, tag) => {
      if (!synth || !canSpeak(tag)) return
      synth.cancel() // never talk over yourself
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = tag
      const voice = voiceFor(tag)
      if (voice) utterance.voice = voice
      utterance.rate = 0.95
      synth.speak(utterance)
    },
    [synth, canSpeak, voiceFor],
  )

  const stop = useCallback(() => synth?.cancel(), [synth])

  return { supported: !!synth, canSpeak, speak, stop }
}
