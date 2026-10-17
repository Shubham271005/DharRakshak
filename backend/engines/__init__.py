"""
Decision engines (Component 6): turn the model output, weather and crop
profile into a risk estimate (F3), ranked action cards (F2) and an
explanation (F4).

    facts.py    — gathers every input into one `Facts` object
    risk.py     — scores rules from shared/content/risk_rules.json
    actions.py  — picks cards from shared/content/action_cards.json
    explain.py  — writes the "Why?" summary from the risk reasons
    content.py  — loads the JSON content and fills {placeholders}

All farmer-facing text and every threshold live in shared/content/, so an
agronomist can review or change them without touching code.
"""
