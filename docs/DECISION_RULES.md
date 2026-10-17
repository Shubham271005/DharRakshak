# How DharRakshak decides: risk, actions and explanations

This page explains in plain language how the app turns a leaf photo into a risk estimate, action cards and a "Why?" explanation (features F3, F2 and F4). Show it to judges, mentors or an agricultural expert for review.

> **These rules are transparent heuristics chosen by the team for the hackathon MVP. They have not been validated by agronomists.** The result is always shown as an *estimate*, and every analysis asks the farmer to verify with local experts.

The exact numbers and all farmer-facing text are in `shared/content/risk_rules.json` and `shared/content/action_cards.json`. You can change them without touching code.

## Inputs

| Input | Source |
|---|---|
| What the photo shows (top class, confidence) | Image model (Component 4) |
| Whether the photo is unclear | Confidence below 50%, or a blank, dark or tiny photo |
| Whether the photo shows a different crop than the profile | Model's crop vs the registered crop |
| Recent and forecast weather | Open-Meteo (Component 5). It may be unavailable. |
| Crop growth stage | Farmer's crop profile |

Each of the 38 classes has a **type** describing how the problem spreads: fungal (19), bacterial (3), viral by contact (1), insect-spread (2), pest (1), healthy (12). The type decides which weather matters.

## Risk score

Each rule that applies adds points **and** a sentence for the explanation.

| Rule | Points | When |
|---|---|---|
| Photo closely matches a disease | 3 | Disease with confidence ≥ 80% |
| Photo may match a disease | 2 | Disease with confidence 50–80% |
| Unclear photo | 1 | Confidence < 50% or a poor photo |
| Leaf looks healthy | 0 | Healthy class, confident |
| Wet weather recently | 2 | Fungal/bacterial **and** (rain ≥ 10 mm **or** humidity ≥ 80% over the last 3 days) |
| Rain expected | 1 | Fungal/bacterial **and** (≥ 5 mm **or** ≥ 60% chance in the next 3 days) |
| Hot and dry | 2 | Spider mites **and** temperature ≥ 28°C **and** humidity < 60% |
| Wet weather, healthy leaf | 1 | Healthy leaf **and** wet recently (stay alert) |
| Sensitive stage | 1 | A problem was found **and** the crop is flowering or fruiting |
| Different crop in the photo | 0 | Shown for transparency only |
| Weather unavailable | 0 | Shown for transparency only |

**Score to level:** 0–2 is **low**, 3–4 is **moderate**, 5 or more is **elevated**.

**Example:** tomato early blight at 90%, 27.7 mm of recent rain, rain forecast, flowering. That's 3 + 2 + 1 + 1 = **7, elevated**.

## Action cards

The app finds every card that applies, sorts them by weight, and shows the top 3:

| Card | Weight | Applies when |
|---|---|---|
| Retake the photo | 100 | Photo unclear |
| Check the crop in the photo | 95 | Different crop than the profile |
| Inspect nearby plants | 90 | Disease or pest found |
| Look under the leaves | 88 | Spider mites |
| Check for small insects | 88 | Insect-spread disease (whitefly, psyllid) |
| Keep checking regularly | 85 | Leaf looks healthy |
| Check local guidance | 80 | Disease found or photo unclear |
| Wash hands and tools | 75 | Contact-spread virus (mosaic) |
| Keep leaves dry | 70 | Fungal/bacterial or healthy **and** wet recently or rain expected |
| Watch the weather | 60 | Fungal/bacterial **and** rain expected |
| Check again in 3–5 days | 50 | Always (fills remaining space) |

**Safety:** cards only suggest checking, verifying, monitoring and basic hygiene. **No pesticide names, products or doses.** An automated test blocks such words in English and Hindi.

## Explanation ("Why?")

- **Summary:** "Inspection priority is *level* (an estimate) because: …" followed by up to 3 reason sentences, in the order the rules ran (photo, then crop check, then weather, then stage). When there are too many, the weakest are dropped.
- **Verify line:**
  - Disease found: "This is not a confirmed diagnosis. Check nearby plants and confirm with your local agriculture extension office or Krishi Vigyan Kendra."
  - Photo unclear: "The photo was unclear, so this result is not reliable. Retake the photo…"
  - Healthy: "Leaves can look healthy early in an infection. Keep checking every few days…"

## Known limitations

- The weather thresholds are generic. Different diseases prefer different conditions; for example, late blight favours cool, wet weather and early blight warm, humid weather. Disease-specific rules need expert input.
- The engine only reasons about the 38 classes the model knows. Nutrient deficiencies and other diseases aren't covered.
- If the model is confidently wrong, as on non-leaf photos (see `MODEL_CARD.md`), the rules will be confidently wrong too. The "verify" line is the safeguard.
