/*
 * SCREEN: Ask DharRakshak — multilingual chatbot (F7) + app-wide polish (F6)
 * OWNER:  Teammate 4
 * DATA:   sendChat(cropId, message, lang) -> ChatReply
 *         Fields: docs/CONTRACT.md, row "Chatbot + language + theme"
 *
 * Mock mode / backend skeleton answer by keyword. Try:
 *   "लोन के लिए कौन से कागज़ बाकी हैं?"
 *   "Why should I inspect nearby plants?"
 *   "Which pesticide should I spray?"   (→ polite refusal)
 * The real grounded chatbot arrives in Component 9; this screen won't change.
 *
 * ========================================================================
 * YOUR TASK — step by step (delete each TODO once it's done)
 * ========================================================================
 * Run the app:  cd frontend && npm run dev   → http://localhost:5173
 *
 * TODO 1  History. Keep messages so they survive switching screens:
 *           const [history, setHistory] = useSessionState('chat.history', [])
 *         Each item: { role: 'user' | 'assistant', text, isFallback }.
 *         Draw them as bubbles: user on the right (bg-moss text-white),
 *         assistant on the left (bg-white border border-tint).
 *         Wrap the list in a scrollable box: "h-[28rem] overflow-y-auto".
 *
 * TODO 2  Input. A <form> with a text <input> and a Send button.
 *         On submit: add the user message, call
 *           const reply = await sendChat(cropId, text, lang)
 *         and add { role: 'assistant', text: reply.reply, isFallback: reply.is_fallback }.
 *         Disable the input and show "…" while waiting. Show <ErrorBox>
 *         if sendChat throws. Placeholder text via t(...).
 *
 * TODO 3  Honesty cues. Under a fallback answer show a small text-muted
 *         note: "Chatbot offline — saved answer". Add a "Clear chat" button.
 *
 * TODO 4  Suggested questions. 2–3 rounded buttons (one Hindi, one
 *         English) that send that question when clicked — makes the live
 *         demo smooth.
 *
 * TODO 5  App polish. Make all four screens feel like one product: check
 *         spacing, card styles and colours across screens; improve
 *         src/components/ui.jsx and src/components/Sidebar.jsx with the
 *         other teammates. Use only the theme colours from src/index.css.
 *
 * TODO 6  Language check. Switch EN ↔ हिंदी on every screen and list any
 *         untranslated text for its owner.
 *
 * DONE WHEN
 *   [ ] The three sample questions give the matching answers.
 *   [ ] History stays when you switch screens and come back.
 *   [ ] Fallback replies are clearly marked.
 *   [ ] All four screens share one consistent look, on phone and laptop.
 */
import { sendChat } from '../api/client.js'
import { useApiData } from '../api/useApiData.js'
import { ErrorBox, Loading, RawData, ScreenHeader, StubBanner } from '../components/ui.jsx'
import { useLanguage } from '../i18n/LanguageContext.jsx'

export default function ChatScreen({ cropId }) {
  const { lang, t } = useLanguage()

  // Temporary: one real round-trip so you can see what a reply looks like.
  // Remove this when TODO 1–2 are finished.
  const question = lang === 'hi' ? 'लोन के लिए कौन से कागज़ बाकी हैं?' : 'Why should I inspect nearby plants?'
  const { data: reply, loading, error, reload } = useApiData(() => sendChat(cropId, question, lang), [cropId, lang])

  return (
    <section>
      <ScreenHeader title={t('nav_chat')} />
      <StubBanner owner="Teammate 4" />
      {loading && <Loading />}
      {error && <ErrorBox error={error} onRetry={reload} />}
      {reply && <RawData data={{ question, reply }} />}
    </section>
  )
}
