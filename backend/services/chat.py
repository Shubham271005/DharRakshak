"""
Grounded multilingual chatbot (Component 9, feature F7).

For every question the backend sends the LLM:
1. SYSTEM RULES — who it is, safety rules, reply language, plain text only
   (replies may be read aloud by the voice assistant).
2. CONTEXT — this farmer's saved data as JSON: crop profile, latest leaf
   analysis (possibilities, risk reasons, action cards), weather, and the
   MOCK loan summary (missing documents, schemes).
3. HISTORY — the last few turns, so follow-up questions make sense.
4. The farmer's QUESTION.

Two safety layers:
- the rules tell the model never to name pesticides or give doses and
  never to promise loan approval;
- `_guard()` checks every reply for dose-like wording (e.g. "2 ml per litre")
  and replaces it with a safe referral if found.

If Groq is unreachable or no key is set, the saved demo answers from
sample_store.mock_chat_reply are used and the reply is marked
`is_fallback=true`, so the UI can say so.
"""

from __future__ import annotations

import json
import logging
import re

from backend import repository
from backend.engines.content import message
from backend.sample_store import mock_chat_reply
from backend.services import llm
from shared.contract import ChatReply, ChatRequest, CropProfile

log = logging.getLogger("dharrakshak.chat")

HISTORY_TURNS = 8      # earlier messages sent for context
MAX_REPLY_TOKENS = 450  # ~4 short sentences + room for Hindi script

# How to ask the model for each language. Haryanvi and Bhojpuri are mostly
# spoken languages: ask for natural dialect in Devanagari, simple words.
LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (Devanagari script)",
    "mr": "Marathi (Devanagari script)",
    "pa": "Punjabi (Gurmukhi script)",
    "bgc": "Haryanvi (the dialect spoken in rural Haryana, written in Devanagari; use natural Haryanvi words, keep it easy to understand)",
    "bho": "Bhojpuri (as spoken in Bihar and eastern Uttar Pradesh, written in Devanagari; use natural Bhojpuri words, keep it easy to understand)",
}

SYSTEM_RULES = """You are DharRakshak (धररक्षक), a friendly farming assistant for small farmers in India.

Use the CONTEXT about this farmer (their crop, latest leaf check, weather and loan) to answer. You may add general, safe farming knowledge. If the context doesn't contain the answer and you are not sure, say you don't know and suggest who to ask.

Safety rules — always follow them:
- Never name any pesticide, fungicide, insecticide or chemical product, and never give doses, mixing amounts or spray schedules. For any treatment question, say that the right treatment depends on the crop and region and ask the farmer to confirm with their local agriculture extension office or Krishi Vigyan Kendra.
- Leaf-check results are possibilities, not confirmed diagnoses. Say so when you talk about them. Risk levels are estimates.
- Loan information in the context is SAMPLE (mock) data, not from a real bank. Never promise that a loan will be approved, and never invent amounts, dates, interest rates or eligibility. Tell the farmer to confirm loan and scheme details with their bank or the official portal.
- For documents, only say which ones are missing or submitted. Don't claim that submitting them completes, speeds up or guarantees anything, and don't invent where or how to submit them (no websites, apps or offices that aren't in the context) — just say to confirm with the bank.
- Never ask for or repeat personal ID numbers, bank account numbers or passwords.

Style:
- Reply in {language}, even if the question uses another language.
- Plain text only: no markdown, no bullet symbols, no emojis — your reply may be read aloud.
- Keep it short: 2 to 4 simple sentences a farmer can act on."""

# Dose-like patterns that must never reach the farmer (second safety layer).
_DOSE_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*(ml|मिली|g|gm|gram|grams|ग्राम|kg|किलो|litre|liter|लीटर|%)\s*(/|per|प्रति)",
    re.IGNORECASE,
)
def _guard(reply: str, lang: str) -> str:
    """Replace any reply that contains dose-like wording (text in every
    language: shared/content/messages.json → chat_safe_referral)."""
    if _DOSE_PATTERN.search(reply):
        log.warning("Blocked a reply containing dose-like wording.")
        return message("chat_safe_referral").in_lang(lang)
    return reply


def build_context(crop: CropProfile) -> tuple[dict, list[str]]:
    """This farmer's saved data as a compact dict, plus which parts were included."""
    used = ["crop_profile"]
    context: dict = {
        "crop_profile": {
            "farmer_name": crop.farmer_name,
            "crop": crop.crop_type,
            "variety": crop.variety or "not recorded",
            "stage": crop.stage.value,
            "days_since_sowing": crop.days_since_sowing,
            "area_acres": crop.area_acres,
            "location": crop.location.name,
        }
    }

    analyses = repository.list_analyses(crop.crop_id, limit=1)
    if analyses:
        a = analyses[0]
        used.append("analysis")
        context["latest_leaf_check"] = {
            "date": a.created_at.date().isoformat(),
            "is_sample_data": a.is_demo,
            "photo_unclear": a.uncertain,
            "photo_may_show_different_crop": a.crop_mismatch,
            "possibilities": [f"{p.display_name.en} ({round(p.confidence * 100)}%)" for p in a.predictions],
            "risk_estimate": a.risk.level.value,
            "risk_reasons": [r.text.en for r in a.risk.reasons],
            "action_cards": [f"{c.priority}. {c.title.en}: {c.detail.en}" for c in a.action_cards],
        }
        if a.weather is not None:
            used.append("weather")
            context["weather"] = a.weather.summary.en

    loan = repository.get_loan_summary(crop.crop_id)
    if loan is not None:
        used.append("loan_summary")
        missing = [d.name.en for d in loan.documents if not d.submitted]
        context["loan"] = {
            "data_source": f"{loan.data_source} (sample data, not from a real bank)",
            "loan": loan.loan.display_name.en,
            "status": loan.loan.status.value,
            "outstanding_inr": loan.loan.outstanding_amount_inr,
            "next_repayment": (
                f"INR {loan.loan.next_repayment.amount_inr} due {loan.loan.next_repayment.due_date.isoformat()}"
                if loan.loan.next_repayment else "none"
            ),
            "documents_submitted": [d.name.en for d in loan.documents if d.submitted],
            "documents_missing": missing,
            "schemes_to_check": [f"{s.name.en}: {s.summary.en}" for s in loan.schemes],
        }
    else:
        context["loan"] = "No loan records for this farmer."
    return context, used


def answer(request: ChatRequest, crop: CropProfile) -> ChatReply:
    """Grounded reply in the requested language, or a marked fallback."""
    lang = request.lang if request.lang in LANGUAGE_NAMES else "en"
    context, used = build_context(crop)

    messages = [
        {"role": "system", "content": SYSTEM_RULES.format(language=LANGUAGE_NAMES[lang])},
        {"role": "system", "content": "CONTEXT (this farmer's saved data):\n" + json.dumps(context, ensure_ascii=False)},
    ]
    for turn in request.history[-HISTORY_TURNS:]:
        messages.append({"role": turn.role, "content": turn.text})
    messages.append({"role": "user", "content": request.message})

    try:
        reply, model = llm.chat_complete(messages, max_tokens=MAX_REPLY_TOKENS)
    except llm.LLMUnavailable as err:
        log.warning("Chatbot falling back to saved answers: %s", err)
        fallback = mock_chat_reply(request)
        return fallback.model_copy(update={"is_fallback": True})

    log.info("Chat answered by %s", model)
    return ChatReply(reply=_guard(reply, lang), lang=lang, used_context=used, is_fallback=False)
