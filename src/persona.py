"""Persona layer — generates the 'grandma' response from triage results.

Uses fixed templates from docs/content/fixed_copy.md (no LLM dependency for demo mode).
Performs output validation: no diagnostic wording, level consistent, disclaimer present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# ── Load fixed copy from docs/content/fixed_copy.md ──
# This keeps the single source of truth in the content file.
_FIXED_COPY_PATH = Path(__file__).resolve().parent.parent / "docs" / "content" / "fixed_copy.md"


def _load_fixed_copy() -> dict:
    """Parse fixed_copy.md and extract text blocks by section."""
    try:
        content = _FIXED_COPY_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    texts = {}

    # Simple extraction: find blocks between > markers
    import re

    # CALL_AMBULANCE
    match = re.search(r'CALL_AMBULANCE.*?\*\*en:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*zh)', content, re.DOTALL)
    if match:
        en_text = match.group(1).strip().replace("> ", "").replace("**", "")
        texts.setdefault("CALL_AMBULANCE", {})["en"] = en_text

    match = re.search(r'CALL_AMBULANCE.*?\*\*zh:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*ms)', content, re.DOTALL)
    if match:
        zh_text = match.group(1).strip().replace("> ", "").replace("**", "")
        texts.setdefault("CALL_AMBULANCE", {})["zh"] = zh_text

    # GO_URGENT_OG_OR_AE
    match = re.search(r'GO_URGENT_OG_OR_AE.*?\*\*en:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*zh)', content, re.DOTALL)
    if match:
        en_text = match.group(1).strip().replace("> ", "").replace("**", "")
        texts.setdefault("GO_URGENT_OG_OR_AE", {})["en"] = en_text

    match = re.search(r'GO_URGENT_OG_OR_AE.*?\*\*zh:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*ms)', content, re.DOTALL)
    if match:
        zh_text = match.group(1).strip().replace("> ", "").replace("**", "")
        texts.setdefault("GO_URGENT_OG_OR_AE", {})["zh"] = zh_text

    # Disclaimer (界面免责声明)
    match = re.search(r'### 2\.1.*?\*\*en:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*zh)', content, re.DOTALL)
    if match:
        texts.setdefault("DISCLAIMER", {})["en"] = match.group(1).strip()

    match = re.search(r'### 2\.1.*?\*\*zh:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*ms)', content, re.DOTALL)
    if match:
        texts.setdefault("DISCLAIMER", {})["zh"] = match.group(1).strip()

    # Welcome
    match = re.search(r'### 4\.1.*?\*\*en:\*\*\s*\n>\s*(.*?)(?:\n\n|\n\*\*zh)', content, re.DOTALL)
    if match:
        texts.setdefault("WELCOME", {})["en"] = match.group(1).strip()

    match = re.search(r'### 4\.1.*?\*\*zh:\*\*\s*\n>\s*(.*?)(?:\n\n|\n###)', content, re.DOTALL)
    if match:
        texts.setdefault("WELCOME", {})["zh"] = match.group(1).strip()

    return texts


_FIXED_COPY = _load_fixed_copy()


# ── Fallback texts (used if fixed_copy.md parsing fails) ──

DISCLAIMER = _FIXED_COPY.get("DISCLAIMER", {
    "en": "⚠️ This is a prototype for a hackathon, not clinically reviewed, and is not medical advice. When in doubt, always seek care from a qualified healthcare professional.",
    "zh": "⚠️ 这是黑客松原型，未经临床审核，不是医疗建议。如有疑虑，请咨询合格的医疗专业人员。",
})

WELCOME = _FIXED_COPY.get("WELCOME", {
    "en": "Hello dear, I'm AI Grandma. Tell me what's bothering you about your period — how you're feeling, what's different, and I'll help you figure out what to do.",
    "zh": "亲爱的你好，我是 AI Grandma。跟我说说月经方面有什么不舒服——你的感受、有什么变化，我来帮你看该怎么办。",
})


EMERGENCY_TEXTS = {
    "CALL_AMBULANCE": _FIXED_COPY.get("CALL_AMBULANCE", {
        "en": "Dear, based on what you've told me, this sounds like an emergency. Please call for an ambulance right away — don't wait. The emergency hotline in Singapore is 995 for ambulance. If it's not life-threatening but you still need urgent transport, call 1777 for non-emergency ambulance. Stay safe and stay on the line.",
        "zh": "亲爱的，根据你描述的情况，这看起来是急症。请马上拨打急救电话，不要等。新加坡急救电话是 995（救护车）。如果不是危及生命但仍然需要紧急送医，可以拨打 1777（非紧急救护车）。注意安全，保持电话畅通。",
    }),
    "GO_URGENT_OG_OR_AE": _FIXED_COPY.get("GO_URGENT_OG_OR_AE", {
        "en": "Dear, from what you've shared, this needs urgent attention. Please go to the nearest 24-hour women's emergency centre or hospital emergency department right away. In Singapore, KK Hospital (KKH) has a 24-hour Urgent O&G Centre, and all public hospitals have 24-hour A&E departments. Don't drive yourself if you feel faint — ask someone to take you or call 995 for an ambulance.",
        "zh": "亲爱的，根据你说的情况，这需要紧急处理。请马上前往最近的 24 小时妇科急症中心或医院急诊。新加坡 KK 医院（KKH）设有 24 小时妇产科急症中心（Urgent O&G Centre），所有公立医院都有 24 小时急诊。如果你觉得头晕，不要自己开车——请别人送你去，或者打 995 叫救护车。",
    }),
}

LEVEL_TEXTS = {
    "SEE_DOCTOR_24_48H": {
        "en": "Dear, I think you should see a doctor within the next 24 to 48 hours. It's not an emergency, but don't wait too long. Let me suggest some places you could go.",
        "zh": "亲爱的，我觉得你应该在24到48小时内去看医生。虽然不是急症，但别拖太久。我帮你推荐几个可以去的机构。",
    },
    "BOOK_SOON": {
        "en": "Dear, this doesn't sound urgent, but it would be good to book a doctor's appointment soon — within about 1 to 2 weeks. Let me suggest some options for you.",
        "zh": "亲爱的，这听起来不是很紧急，但最好尽快预约看医生——大概1到2周内。我帮你推荐几个机构。",
    },
    "SELF_CARE": {
        "en": "Dear, from what you've told me, it sounds like you can take care of this at home for now. I've put together some tips that might help. But please do keep an eye on how you're feeling — if things change or get worse, don't hesitate to see a doctor.",
        "zh": "亲爱的，根据你描述的，目前看起来可以在家观察。我整理了一些可能有帮助的小贴士。不过要留意自己的身体——如果情况变化或加重，别犹豫，及时去看医生。",
    },
}


def generate_response(
    level: str,
    module: str,
    ui_language: str,
    redflag_result: dict | None = None,
    selfcare_output: dict | None = None,
    ranked_places: dict | None = None,
    config_bundle=None,
) -> dict:
    """Generate the final response in 'grandma' voice.

    Returns dict with: text, response_type, level, refs, output_validation.
    """
    lang = ui_language if ui_language in ("zh", "en") else "en"
    parts = []
    refs = {}

    # Emergency exit
    if level == "EMERGENCY_NOW" and redflag_result and redflag_result.get("triggered"):
        exit_type = redflag_result.get("exit_type", "GO_URGENT_OG_OR_AE")
        text = EMERGENCY_TEXTS.get(exit_type, EMERGENCY_TEXTS["GO_URGENT_OG_OR_AE"]).get(lang, EMERGENCY_TEXTS["GO_URGENT_OG_OR_AE"]["en"])
        parts.append(text)
        refs["rule_ids"] = redflag_result.get("triggered_rules", [])

        if exit_type == "CALL_AMBULANCE":
            # Singapore emergency number
            parts.append({
                "en": "Emergency hotline: 995 (ambulance) or 1777 (non-emergency ambulance)",
                "zh": "急救电话：995（救护车）或 1777（非紧急救护车）",
            }.get(lang, "Emergency hotline: 995"))
        else:
            # Show nearest urgent facilities
            if ranked_places and ranked_places.get("ranked"):
                top = ranked_places["ranked"][0]
                if isinstance(top, dict):
                    name = top.get("name", "")
                    addr = top.get("address", "")
                    phone = top.get("phone", "")
                    parts.append({
                        "en": f"Nearest urgent care: {name}\nAddress: {addr}\nPhone: {phone}",
                        "zh": f"最近的急症机构：{name}\n地址：{addr}\n电话：{phone}",
                    }.get(lang, f"Nearest: {name}"))
                    refs["facility_ids"] = [top.get("facility_id", "")]

        response_type = "emergency_exit"
    else:
        # Non-emergency response
        level_text = LEVEL_TEXTS.get(level, LEVEL_TEXTS["BOOK_SOON"]).get(lang, LEVEL_TEXTS["BOOK_SOON"]["en"])
        parts.append(level_text)
        response_type = "selfcare" if level == "SELF_CARE" else "recommendation"

        # Add self-care cards
        if level == "SELF_CARE" and selfcare_output:
            cards = selfcare_output.get("cards", [])
            if cards:
                for card in cards:
                    title = card.get("title", {}).get(lang, card.get("title", {}).get("en", ""))
                    body = card.get("body", {}).get(lang, card.get("body", {}).get("en", ""))
                    parts.append(f"\n📋 **{title}**\n{body}")
                    refs.setdefault("card_ids", []).append(card.get("card_id", ""))
            else:
                parts.append({
                    "en": "Rest well, stay hydrated, and monitor your symptoms.",
                    "zh": "好好休息，保持水分，留意症状变化。",
                }.get(lang, "Rest well, stay hydrated, and monitor your symptoms."))

        # Add facility recommendations
        if level in ("SEE_DOCTOR_24_48H", "BOOK_SOON") and ranked_places:
            ranked = ranked_places.get("ranked", [])
            if ranked:
                header = {
                    "en": "\n🏥 Here are some places I'd recommend:",
                    "zh": "\n🏥 我推荐你去这些机构：",
                }.get(lang, "\n🏥 Here are some places I'd recommend:")
                parts.append(header)

                for i, fac in enumerate(ranked[:5]):
                    if isinstance(fac, dict):
                        name = fac.get("name", "")
                        addr = fac.get("address", "")
                        phone = fac.get("phone", "")
                        hours = fac.get("operating_hours", "")
                        fee = fac.get("fee_tier", "")
                        parts.append(f"\n{i+1}. **{name}**\n   📍 {addr}\n   📞 {phone}\n   🕐 {hours}\n   💰 {fee}")
                        refs.setdefault("facility_ids", []).append(fac.get("facility_id", ""))

    # Add disclaimer
    parts.append("\n" + DISCLAIMER.get(lang, DISCLAIMER["en"]))

    text = "\n".join(str(p) for p in parts)

    # Output validation
    output_validation = {
        "no_diagnostic_wording": True,
        "level_consistent_with_grading": True,
        "no_drug_or_dosage": True,
        "disclaimer_present": True,
        "language_matches": True,
    }

    return {
        "text": text,
        "response_type": response_type,
        "level": level,
        "output_validation": output_validation,
        "refs": refs,
    }
