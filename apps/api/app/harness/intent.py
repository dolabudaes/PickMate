from __future__ import annotations

import re
from typing import Any

DEFAULT_INTENT = {
    "category": "any",
    "budget": {"min": None, "max": None},
    "hard_constraints": {
        "in_stock": False,
        "device_platform": "any",
        "form_factor": None,
        "brand_or_store": None,
        "required_terms": [],
        "required_attributes": [],
    },
    "use_cases": [],
    "priorities": {
        "noise_cancellation": 0.45,
        "comfort": 0.45,
        "call_quality": 0.40,
        "battery": 0.40,
        "price_value": 0.60,
        "compatibility": 0.70,
        "water_resistance": 0.20,
        "multipoint": 0.20,
        "quality": 0.62,
        "durability": 0.48,
        "review_confidence": 0.55,
    },
    "small_ear_friendly": False,
    "avoid_deep_insertion": False,
    "dealbreakers": [],
    "explicit_concerns": [],
    "missing_information": [],
    "product_query": "home audio",
    "review_evidence_needs": [],
    "decision_dimensions": ["compatibility", "price_value", "quality"],
    "raw_text": "",
}


class IntentRouter:
    def route(self, text: str, action: str, has_active_run: bool = False) -> str:
        if action == "compare":
            return "PRODUCT_COMPARISON"
        if action == "decide":
            return "PRODUCT_DECISION"
        if action == "price_check":
            return "PRICE_CHECK"
        if action == "preference_update":
            return "PREFERENCE_UPDATE"
        if re.search(r"怎么选|对比|比较|三款|几款|哪个", text):
            return "PRODUCT_COMPARISON"
        if re.search(r"价格|好价|值得买|贵|便宜|现在买", text):
            return "PRICE_CHECK" if not re.search(r"推荐|选", text) else "PRODUCT_RECOMMENDATION"
        if re.search(r"担心|风险|差评|问题|缺点|翻车", text):
            return "PRODUCT_RISK_QUERY"
        if has_active_run and re.search(r"电话|会议|通话|舒适|戴久|降噪|预算|性价比|价格|质量|口碑|评分|耐用|reviews?|rating|quality|durable|phone meeting|conference call|comfort|noise", text, re.I):
            return "PREFERENCE_UPDATE"
        if re.search(r"\d{2,6}|地铁|通勤|小耳|安卓|android|ios|苹果|推荐|find|looking|searching|need|want", text.lower()):
            return "PRODUCT_RECOMMENDATION"
        return "GENERAL_PRODUCT_QUESTION"


def parse_intent(text: str, previous: dict[str, Any] | None = None) -> dict[str, Any]:
    intent = {**DEFAULT_INTENT, **(previous or {})}
    intent["budget"] = {**DEFAULT_INTENT["budget"], **intent.get("budget", {})}
    intent["hard_constraints"] = {**DEFAULT_INTENT["hard_constraints"], **intent.get("hard_constraints", {})}
    intent["priorities"] = {**DEFAULT_INTENT["priorities"], **intent.get("priorities", {})}
    intent["use_cases"] = list(dict.fromkeys(intent.get("use_cases", [])))
    intent["explicit_concerns"] = list(dict.fromkeys(intent.get("explicit_concerns", [])))
    intent["dealbreakers"] = list(dict.fromkeys(intent.get("dealbreakers", [])))
    intent["review_evidence_needs"] = list(dict.fromkeys(intent.get("review_evidence_needs", [])))
    intent["decision_dimensions"] = list(dict.fromkeys(intent.get("decision_dimensions", [])))
    intent["raw_text"] = text or intent.get("raw_text") or DEFAULT_INTENT["raw_text"]

    lower = text.lower()
    budget = extract_budget(text)
    if budget is not None:
        intent["budget"]["max"] = budget
    category = infer_category(text)
    if category:
        intent["category"] = category
    product_query = extract_product_query(text)
    if product_query:
        intent["product_query"] = product_query
    brand = extract_brand_or_store(text)
    if brand:
        intent["hard_constraints"]["brand_or_store"] = brand
    if "android" in lower or "安卓" in text:
        intent["hard_constraints"]["device_platform"] = "android"
    if "iphone" in lower or "ios" in lower or "苹果" in text:
        intent["hard_constraints"]["device_platform"] = "ios"
    if "半入耳" in text:
        intent["hard_constraints"]["form_factor"] = "semi_in_ear"
    elif "入耳" in text:
        intent["hard_constraints"]["form_factor"] = "in_ear"
    if any(k in text for k in ["地铁", "通勤", "公交"]):
        intent["use_cases"].append("subway_commute")
    if any(k in text for k in ["运动", "跑步", "健身", "出汗"]):
        intent["use_cases"].append("sports")
    if re.search(r"办公|办公室|office|work|商务|business", text, re.I):
        intent["use_cases"].append("office")
    if re.search(r"旅行|差旅|travel|trip", text, re.I):
        intent["use_cases"].append("travel")
    if re.search(r"living room|客厅", text, re.I):
        intent["use_cases"].append("living_room")
    if re.search(r"\btv\b|television|电视", text, re.I):
        intent["use_cases"].append("tv")
    if re.search(r"home theater|home theatre|影院", text, re.I):
        intent["use_cases"].append("home_theater")
    if any(k in text.lower() for k in ["电话", "会议", "通话", "开会", "phone meeting", "conference call", "calls every day"]):
        intent["priorities"]["call_quality"] = 0.95
        intent["priorities"]["noise_cancellation"] *= 0.72
        intent["explicit_concerns"].append("call_quality")
        intent["decision_dimensions"].append("call_quality")
    if any(k in text for k in ["耳朵疼", "戴久", "舒服", "舒适", "不胀", "小耳"]):
        intent["priorities"]["comfort"] = 0.95
        intent["small_ear_friendly"] = True
        intent["explicit_concerns"].append("comfort")
        intent["decision_dimensions"].append("comfort")
    if re.search(r"降噪|安静|地铁太吵|noise cancel|anc", text, re.I):
        intent["priorities"]["noise_cancellation"] = 0.95
        intent["decision_dimensions"].append("noise_cancellation")
    if re.search(r"续航|电池|battery", text, re.I):
        intent["priorities"]["battery"] = 0.85
        intent["decision_dimensions"].append("battery")
    if re.search(r"便宜|性价比|省钱|预算|value|budget|affordable|cheap", text, re.I):
        intent["priorities"]["price_value"] = 0.90
        intent["decision_dimensions"].append("price_value")
    if any(k in text for k in ["不喜欢深", "不要深", "塞得很深"]):
        intent["avoid_deep_insertion"] = True
        intent["explicit_concerns"].append("avoid_deep_insertion")
    if re.search(r"防水|出汗|waterproof|water resistant|sweat", text, re.I):
        intent["priorities"]["water_resistance"] = 0.80
        intent["decision_dimensions"].append("water_resistance")
    if re.search(r"多设备|电脑|平板|multipoint|multi device", text, re.I):
        intent["priorities"]["multipoint"] = 0.80
        intent["decision_dimensions"].append("multipoint")
    if re.search(r"兼容|适配|compatible|compatibility|connector|型号|model", text, re.I):
        intent["priorities"]["compatibility"] = 0.88
        intent["explicit_concerns"].append("compatibility")
        intent["decision_dimensions"].append("compatibility")
    if re.search(r"质量|品质|做工|好评|评分|口碑|quality|rating|reviews?|stars?", text, re.I):
        intent["priorities"]["quality"] = 0.86
        intent["priorities"]["review_confidence"] = 0.78
        intent["explicit_concerns"].append("quality")
        intent["decision_dimensions"].extend(["quality", "review_confidence"])
    if re.search(r"耐用|耐久|结实|坏|寿命|durable|durability|long lasting|sturdy", text, re.I):
        intent["priorities"]["durability"] = 0.86
        intent["explicit_concerns"].append("durability")
        intent["decision_dimensions"].append("durability")

    intent["use_cases"] = list(dict.fromkeys(intent["use_cases"]))
    intent["explicit_concerns"] = list(dict.fromkeys(intent["explicit_concerns"]))
    intent["hard_constraints"]["required_attributes"] = merge_required_attributes(
        intent["hard_constraints"].get("required_attributes", []),
        extract_required_attributes(text),
    )
    intent["review_evidence_needs"] = list(dict.fromkeys([*intent.get("review_evidence_needs", []), *extract_review_evidence_needs(text)]))
    intent["decision_dimensions"] = list(dict.fromkeys(intent["decision_dimensions"]))
    normalize_priorities(intent)
    intent["missing_information"] = [] if intent["use_cases"] else ["Primary use case"]
    return intent


def normalize_priorities(intent: dict[str, Any]) -> None:
    values = intent["priorities"]
    total = sum(float(v) for v in values.values()) or 1.0
    for key in list(values.keys()):
        values[key] = round(float(values[key]) / total, 3)


def extract_budget(text: str) -> int | float | None:
    normalized = text.lower()
    contextual = re.search(r"(?:预算|最多|不超过|以内|以下|under|below|less than|no more than|budget|[$¥￥])\s*[$¥￥]?\s*(\d+(?:\.\d+)?)", normalized)
    if contextual:
        return number(contextual.group(1))
    bare_limit = re.search(r"(\d+(?:\.\d+)?)\s*(?:以内|以下|内)", normalized)
    if bare_limit:
        return number(bare_limit.group(1))
    trailing = re.search(r"[$¥￥]?\s*(\d+(?:\.\d+)?)\s*(?:元|块|rmb|人民币|美元|usd|dollars?|刀)\s*(?:以内|以下|内|or less)?", normalized)
    if trailing:
        return number(trailing.group(1))
    return None


def infer_category(text: str) -> str:
    normalized = text.lower()
    if re.search(r"sound ?bars?", normalized):
        return "soundbar"
    if re.search(r"receivers?|av receiver", normalized):
        return "receiver"
    if re.search(r"amplifiers?|amps?\b", normalized):
        return "amplifier"
    if re.search(r"home theaters?|surround", normalized):
        return "home theater"
    if re.search(r"speakers?", normalized):
        return "speaker"
    if re.search(r"hdmi|optical|toslink|cables?", normalized):
        return "cable"
    if re.search(r"earbuds?|headphones?|headset", normalized):
        return "headphones"
    return ""


def extract_product_query(text: str) -> str:
    english = re.search(r"(?:find me|looking for|searching for|need|want)\s+(?:a|an|the|some|set of)?\s*([^.,;，。]+)", text, re.I)
    if english:
        return clean_product_query(english.group(1))
    chinese = re.search(r"(?:买|找|推荐|想要|需要)([^，。,.;]+)", text)
    if chinese:
        return clean_product_query(chinese.group(1))
    return clean_product_query(text)


def clean_product_query(value: str) -> str:
    value = re.sub(r"\d+(?:\.\d+)?\s*(元|块|美元|usd|dollars?|以内|以下|预算|items?|stars?)", " ", value, flags=re.I)
    value = re.sub(r"(预算|以内|以下|地铁|通勤|小耳|安卓|android|ios|苹果|舒适|舒服|降噪|性价比|便宜|quality|reviews?|rating|durable|compatible|with reviews mentioning.*)$", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()[:80]


def extract_brand_or_store(text: str) -> str:
    by_brand = re.search(r"\bby\s+([A-Z][A-Za-z0-9&.\- ]{1,40})(?:\s+that|\s+with|,|\.|$)", text)
    if by_brand:
        return by_brand.group(1).strip()
    chinese = re.search(r"(?:品牌|店铺|店家|商家)[：:\s]*([\w\u4e00-\u9fa5 .&-]{2,30})", text)
    return chinese.group(1).strip() if chinese else ""


def extract_required_attributes(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    item_count = re.search(r"(?:exactly|正好|刚好)\s*(\d+)\s*(?:items?|个|支|件|pack)", text, re.I)
    if item_count:
        out.append({"field": "Number of Items", "value": item_count.group(1), "source": "query"})
    material = re.search(r"(?:made from|made of|材质|材料)[^\w\u4e00-\u9fa5]*([A-Za-z\u4e00-\u9fa5 ]{3,60})(?:[,.，。]|$)", text, re.I)
    if material:
        out.append({"field": "Material", "value": material.group(1).strip(), "source": "query"})
    size = re.search(r"(?:measures?|尺寸|大小|size)[^\w]*(\d+(?:[.\-x×/ ]+\d+)+(?:\s*inches?|\s*inch|厘米|cm)?)", text, re.I)
    if size:
        out.append({"field": "Size", "value": size.group(1).strip(), "source": "query"})
    return out


def extract_review_evidence_needs(text: str) -> list[str]:
    out: list[str] = []
    review_phrase = re.search(r"reviews?\s+(?:that\s+)?(?:mention|mentioning|say|saying)\s+(.+?)(?:\.|, finally| additionally|$)", text, re.I)
    if review_phrase:
        out.extend(part.strip() for part in re.split(r"\s+and\s+|[,;，；]", review_phrase.group(1)) if part.strip())
    chinese = re.search(r"(?:评论|评价|口碑).*(?:提到|说|反馈)([^。；;]+)", text)
    if chinese:
        out.extend(part.strip() for part in re.split(r"[，、和]", chinese.group(1)) if part.strip())
    return [item for item in out if len(item) > 1][:6]


def merge_required_attributes(existing: list[dict[str, Any]], incoming: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_key = {f"{item.get('field', '').lower()}={str(item.get('value', '')).lower()}": item for item in existing}
    for item in incoming:
        by_key[f"{item['field'].lower()}={item['value'].lower()}"] = item
    return list(by_key.values())


def number(value: str) -> int | float:
    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed
