# Live demo script (about 4 minutes)

**Setup, 10 minutes before:**
- Run `python scripts/reset_db.py`, then `./scripts/run_demo.sh`.
- Open **http://localhost:5173** in Chrome and allow the microphone.
- Have 2 demo leaf photos ready, already tested with `scripts/try_model.py`. A clear tomato leaf with visible spots works best.
- Close other tabs. Turn the laptop volume up for the spoken answers.

| # | Screen | Do | Say |
|---|---|---|---|
| 1 | **My crop** | Show the profile card and the weather card | "A tomato field in Sonipat, flowering, about 50 days after sowing (the day count updates daily). The weather is live from Open-Meteo." |
| 2 | **Leaf check** | Upload the demo photo and press *Check this leaf* | "The model gives ranked possibilities, never a confirmed diagnosis." |
| 3 | | Point at the risk estimate, the reasons and their points | "The risk is an **estimate**. Every point has a reason: what the photo shows, recent rain, the flowering stage." |
| 4 | | Point at the 3 action cards, then open one *Why?* | "Safe next steps only: inspect, confirm locally, keep leaves dry. No pesticide advice." |
| 5 | | Switch the sidebar to **हिंदी** | "Everything is in Hindi: cards, reasons, explanation." |
| 6 | **लोन और कागज़ात** | Tick *ज़मीन के रिकॉर्ड की कॉपी* (land record copy), and watch 3/5 become 4/5 | "This is **sample** loan data. We are not connected to any bank. The checklist shows what's still missing." |
| 7 | **धररक्षक से पूछें** | Tap 🎤 and say *"लोन के लिए कौन से कागज़ बाकी हैं?"* ("Which loan documents are still missing?"), then tap ■ | "The farmer can just speak. The answer uses their own saved data and is read aloud." |
| 8 | | Type *"Which pesticide should I spray and how much?"* | "It refuses doses and sends the farmer to the Krishi Vigyan Kendra. That's by design." |
| 9 | **Leaf check** | Scroll to *Earlier checks* | "Every check is saved, so the farmer can track the crop over the season." |

## If something goes wrong

| Problem | Do this |
|---|---|
| The model gives a strange answer | Say: "It's a possibility; that's why we show the top 3 and ask the farmer to verify." Then use the second photo. |
| The mic doesn't work | Type the same question; the chat is identical. Voice needs Chrome and microphone permission. |
| No spoken answer in Hindi | That device has no Hindi voice (the app shows a note). English answers still speak. |
| A chat answer says "saved answer" | Groq is unreachable, and the app is showing its built-in fallback answers. Say so honestly. |
| "Weather unavailable" | No internet at the venue. The analysis still works, and the app never invents weather. |
| The app won't start | Check that nothing else is using ports 8000 or 5173, or run `API_PORT=8001 WEB_PORT=5174 ./scripts/run_demo.sh`. |
