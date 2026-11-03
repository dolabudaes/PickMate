from __future__ import annotations

import re
from typing import Any

from .launch_demo import BASICS_ID, DVI_ID, KABEL_ID, TOZO_ID
from .shopping_compare import reference_amount

GAMING_120 = re.compile(r"4k.{0,12}120|120\s*hz|4k gaming|good for my ps5|can it do 120", re.I)
CHEAPER_BASICS = re.compile(r"cheaper amazon|amazon basics|something cheaper|what about the cheaper", re.I)
WORTH_IT = re.compile(r"extra cost|worth it|is it worth", re.I)
TAKE_FIRST = re.compile(r"go with the first|take the first|i('ll| will) (go with|take) (this|that|the kabel|kabel)", re.I)
OLD_MONITOR = re.compile(r"connect my laptop|older monitor|old monitor", re.I)
HAS_PORTS = re.compile(r"laptop has hdmi|monitor uses dvi|only need 1080", re.I)
WHY_HDMI = re.compile(r"why can'?t|normal hdmi|regular hdmi|just use a (normal|regular) hdmi|adapter", re.I)
TASTE = re.compile(r"compatibility matters more|care more about compatibility|remember that i care", re.I)
WHICH_CABLE = re.compile(r"which cable should i buy|so which cable|which one should i buy", re.I)
CLARIFY_PORT = re.compile(r"^(hdmi|dvi|vga|not sure)\.?$", re.I)
GAMING_OPEN = re.compile(r"tv runs.{0,20}4k\s*60.{0,60}upgrade.{0,20}120", re.I)
RELIABILITY_REVIEWS = re.compile(r"reviews?.{0,40}(reliable|working|months)|more expensive.{0,30}reliable", re.I)
PERSONALIZED_CHOICE = re.compile(r"knowing how i shop.{0,30}(choose|pick)", re.I)
STAY_60 = re.compile(r"what if.{0,30}stay at 60|decide to stay at 60", re.I)
KEEP_KABEL = re.compile(r"still planning to upgrade.{0,30}keep.{0,20}kabeldirekt", re.I)
MONITOR_COMPARE = re.compile(r"regular amazon basics.{0,30}(supports|4k).{0,30}better", re.I)
MONITOR_REVIEW = re.compile(r"buyer reviews?.{0,50}(stops working|months)", re.I)
MONITOR_TASTE = re.compile(r"fits? my setup.{0,40}(cheapest|lowest price)", re.I)
KABEL_REVIEW = re.compile(r"(black screens?|connection drops?|dropouts?).{0,50}kabel|kabel.{0,50}(black screens?|connection drops?|dropouts?)", re.I)
MONITOR_DISTANCE = re.compile(r"about two feet|two feet.{0,50}(regret|months)", re.I)
MONITOR_CHEAPER_DEAL = re.compile(r"regular amazon basics hdmi cable.{0,60}(better deal|only \$?8\.55)", re.I)
MONITOR_UPGRADE_VALUE = re.compile(r"kabeldirekt.{0,80}(worth buying|worth getting|upgrade)|what about the kabeldirekt", re.I)
MONITOR_LONG_TERM_TASTE = re.compile(r"paying? a little more.{0,100}features i won'?t use.{0,100}compatibility|compatibility comes first.{0,100}pay a little more.{0,100}features i(?:'ll| will) never use", re.I)
MONITOR_FINAL_CHOICE = re.compile(r"keep the hdmi-to-dvi.{0,100}(current choice|my choice|compare the other two|revisit the other two)|hdmi-to-dvi cable as my current choice", re.I)
TV_STORY_OPEN = re.compile(r"4k tv.{0,80}60\s*hz.{0,100}(eight|8) feet|\$8\.55 amazon basics.{0,80}\$10\.99 kabeldirekt", re.I)
TV_FUTURE_PROOF = re.compile(r"kabeldirekt.{0,60}\$?2\.44.{0,80}future-proof|\$?2\.44 more.{0,80}future-proof", re.I)
TV_RELIABILITY = re.compile(r"how about reliability.{0,80}(cheaper one|safe choice)|cheaper one.{0,50}(reliable|safe)", re.I)
TV_FINAL_CHOICE = re.compile(r"keep the amazon basics 10-foot cable.{0,100}(tv|future monitor)|10-foot cable for the tv", re.I)
EARBUDS_OPEN = re.compile(r"(affordable|budget).{0,50}(wireless earbuds|tozo t10)|tozo t10.{0,50}(think|worth|commut)", re.I)
EARBUDS_NARROW = re.compile(r"mostly music|music on the train|stable connection.{0,30}comfort", re.I)
EARBUDS_ALTERNATIVE = re.compile(r"something better.{0,30}(same|similar) price|better around.{0,20}price", re.I)
EARBUDS_SHORTLIST = re.compile(r"keep.{0,20}tozo.{0,30}shortlist|tozo.{0,30}until i know more", re.I)


def _money(amount: float | None) -> str:
    if amount is None:
        return "Not listed"
    if abs(amount - round(amount)) < 0.001:
        return f"${amount:.0f}"
    return f"${amount:.2f}"


def _price(product: dict[str, Any] | None) -> float | None:
    return reference_amount(product) if product else None


def _id(product: dict[str, Any] | None) -> str:
    return str((product or {}).get("id") or "")


def _ref(product: dict[str, Any], role: str, spec: str) -> dict[str, Any]:
    return {
        "product_id": product.get("id"),
        "role": role,
        "title": _display(product),
        "brand": product.get("brand"),
        "price": _price(product),
        "spec_line": spec,
    }


def _display(product: dict[str, Any]) -> str:
    pid = _id(product)
    if pid == KABEL_ID:
        return "KabelDirekt 8K HDMI Cable · 15ft"
    if pid == BASICS_ID:
        return "Amazon Basics HDMI Cable · 10ft"
    if pid == DVI_ID:
        return "Amazon Basics HDMI to DVI · 3ft"
    if pid == TOZO_ID:
        return "TOZO T10 Wireless Earbuds"
    name = (product.get("name") or "This product").strip()
    return name[:64]


def _by_id(*products: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for product in products:
        if product and product.get("id"):
            out[str(product["id"])] = product
    return out


def try_launch_demo_reply(
    *,
    message: str,
    primary: dict[str, Any] | None,
    alternatives: list[dict[str, Any]],
    comparison_products: list[dict[str, Any]],
    action_status: dict[str, Any] | None,
    session_context: dict[str, Any],
    retrieved_taste: dict[str, Any] | list[str] | None = None,
    memory_enabled: bool = True,
) -> dict[str, Any] | None:
    catalog = _by_id(primary, *(alternatives or []), *(comparison_products or []), session_context.get("_previous_product"))
    text = message or ""

    earbuds = _earbuds_story_reply(
        text,
        retrieved_taste=retrieved_taste,
        memory_enabled=memory_enabled,
        active_product_ids=set(catalog),
    )
    if earbuds:
        return earbuds

    exact = _exact_story_reply(
        text,
        action_status=action_status,
        retrieved_taste=retrieved_taste,
        memory_enabled=memory_enabled,
        session_context=session_context,
        active_product_ids=set(catalog),
    )
    if exact:
        return exact

    if GAMING_120.search(text) and (_id(primary) == KABEL_ID or session_context.get("focus_product_ids", [None])[:1] == [KABEL_ID]):
        product = catalog.get(KABEL_ID) or primary
        if not product:
            return None
        return _pack(
            "COMPATIBILITY",
            "This cable is advertised for 4K at 120Hz, so it's the stronger match for that requirement. Your devices and their HDMI ports also need to support it.",
            [_ref(product, "primary", "Listed 4K@120Hz · 8K@60Hz · 15 ft")],
            [
                {"id": "cheaper", "label": "Compare a cheaper cable", "kind": "message", "message": "What about the cheaper Amazon Basics cable?"},
                {"id": "worth", "label": "Is the extra cost worth it?", "kind": "message", "message": "Is the extra cost worth it?"},
            ],
        )

    if CHEAPER_BASICS.search(text) or WORTH_IT.search(text):
        brief = _hdmi_brief(
            message,
            [KABEL_ID, BASICS_ID],
            session_context,
            retrieved_taste,
            memory_enabled,
            "COMPARE" if CHEAPER_BASICS.search(text) else "TRADEOFF",
        )
        if brief:
            return brief

    if TAKE_FIRST.search(text):
        from . import products as product_service
        kabel = product_service.get_products([KABEL_ID])
        product = kabel[0] if kabel else primary
        saved = bool((action_status or {}).get("saved"))
        line = "Good fit for your 4K 120Hz requirement. You can find it in My Picks." if saved else "Good fit for your 4K 120Hz requirement. Save it to My Picks when you're ready."
        return _pack(
            "ACTION_RESULT" if saved else "RECOMMENDATION",
            line,
            [_ref(product, "primary", "Listed 4K@120Hz · 15 ft")] if product else [],
            [{"id": "view-cart", "label": "View in cart", "kind": "message", "href": "/saved", "message": "Show my cart"}] if saved else [
                {"id": "save", "label": "Save to My Picks", "kind": "message", "message": "Save the first one."}
            ],
            decision_highlight="Saved to My Picks" if saved else None,
        )

    if OLD_MONITOR.search(text) and not HAS_PORTS.search(text) and not CLARIFY_PORT.search(text.strip()):
        return _pack(
            "CLARIFICATION",
            "The connector is the first thing I'd check. Does your monitor use HDMI, DVI, or VGA?",
            [],
            [],
            clarification_options=[
                {"id": "hdmi", "label": "HDMI", "message": "The monitor uses HDMI."},
                {"id": "dvi", "label": "DVI", "message": "My laptop has HDMI, and the monitor uses DVI. I only need 1080p."},
                {"id": "vga", "label": "VGA", "message": "The monitor uses VGA."},
                {"id": "unsure", "label": "Not sure", "message": "I'm not sure what port the monitor uses."},
            ],
        )

    if HAS_PORTS.search(text) or (CLARIFY_PORT.search(text.strip()) and "dvi" in text.lower()):
        from . import products as product_service
        found = product_service.get_products([DVI_ID])
        product = found[0] if found else primary
        if not product:
            return None
        return _pack(
            "RECOMMENDATION",
            "I'd start with the Amazon Basics HDMI-to-DVI cable. It has the connector combination you need, "
            f"its listing covers 1080p, and at {_money(_price(product))} it costs less than the regular HDMI cable you're considering.",
            [_ref(product, "primary", "HDMI ↔ DVI · 1080p")],
            [
                {"id": "view", "label": "View product", "kind": "message", "href": f"/product/{DVI_ID}", "message": "Show details"},
                {"id": "save", "label": "Save to My Picks", "kind": "message", "message": "Save the HDMI-to-DVI cable for me."},
            ],
            decision_highlight="PICKI'S PICK",
        )

    if WHY_HDMI.search(text):
        brief = _hdmi_brief(message, [DVI_ID, BASICS_ID], session_context, retrieved_taste, memory_enabled, "COMPARE")
        if brief:
            return brief

    if TASTE.search(text):
        return _pack(
            "PREFERENCE_UPDATE",
            "I'll prioritize compatibility first, then price, when comparing products for you.",
            [],
            [{"id": "which", "label": "Which cable should I buy?", "kind": "message", "message": "So which cable should I buy?"}],
            decision_highlight="Saved to My Taste",
        )

    if WHICH_CABLE.search(text) or DECISION_SWITCH.search(text):
        ids = [DVI_ID, BASICS_ID] if _looks_monitor(session_context, text) else [KABEL_ID, BASICS_ID]
        brief = _hdmi_brief(message, ids, session_context, retrieved_taste, memory_enabled, "RECOMMENDATION")
        if brief:
            return brief
    return None


DECISION_SWITCH = re.compile(r"planning a 120|staying at 60|prioritize lower price", re.I)


def _looks_monitor(session_context: dict[str, Any], text: str) -> bool:
    blob = f"{session_context.get('need') or ''} {' '.join(str(x) for x in (session_context.get('requirements') or []))} {text}".lower()
    return "dvi" in blob or "older monitor" in blob or "old monitor" in blob


def _looks_tv_story_context(session_context: dict[str, Any], active_product_ids: set[str]) -> bool:
    blob = " ".join(str(item) for item in [
        session_context.get("need") or "",
        session_context.get("category_hint") or "",
        *(session_context.get("devices") or []),
        *(session_context.get("requirements") or []),
    ]).lower()
    context_ids = {
        str(item)
        for key in ("focus_product_ids", "compared_product_ids", "shown_product_ids", "listed_product_ids")
        for item in (session_context.get(key) or [])
    }
    product_ids = context_ids or active_product_ids
    if "dvi" in blob or DVI_ID in product_ids:
        return False
    return "4k" in blob and "60" in blob and ("tv" in blob or "hdmi-to-hdmi" in blob)


def _hdmi_brief(
    message: str,
    product_ids: list[str],
    session_context: dict[str, Any],
    retrieved_taste: dict[str, Any] | list[str] | None,
    memory_enabled: bool,
    reply_type: str,
) -> dict[str, Any] | None:
    from . import products as product_service
    from .decision_brief import compose_decision_brief

    loaded = product_service.get_products(product_ids)
    if len(loaded) < 1:
        return None
    return compose_decision_brief(
        message=message,
        products=loaded,
        shopping_context=session_context,
        retrieved_taste=retrieved_taste,
        memory_enabled=memory_enabled,
        reply_type=reply_type,
    )


def _earbuds_story_reply(
    text: str,
    *,
    retrieved_taste: dict[str, Any] | list[str] | None,
    memory_enabled: bool,
    active_product_ids: set[str],
) -> dict[str, Any] | None:
    if TOZO_ID not in active_product_ids and not EARBUDS_OPEN.search(text):
        return None
    from . import products as product_service

    product = product_service.get_product(TOZO_ID)
    if not product:
        return None
    if EARBUDS_OPEN.search(text):
        personalized = memory_enabled and "reliability" in str(retrieved_taste or {}).lower()
        preference_line = " I remember you care about reliability more than extra features." if personalized else ""
        return _pack(
            "RECOMMENDATION",
            f"At {_money(_price(product))}, the TOZO T10 is worth considering as a budget option.{preference_line} The available review evidence may help with sound and value, but I would want stronger evidence before making a claim about long-term connection stability. Will you use them more for music or calls?",
            [_ref(product, "primary", "Bluetooth 5.3 · wireless charging case")],
            [{"id": "music", "label": "Mostly music", "kind": "message", "message": "Mostly music on the train. I care about a stable connection and comfort more than fancy features."}],
        )
    if EARBUDS_NARROW.search(text):
        sections, status = _review_evidence([product], before="comfort during longer sessions and the return policy")
        return _pack(
            "REVIEWS",
            "Then I would put everyday comfort and connection reliability ahead of the feature list. The price is appealing, but the available evidence is not strong enough to call long-session comfort or connection stability proven.",
            [],
            [{"id": "similar", "label": "Find a similar-price option", "kind": "message", "message": "Is there something better around the same price?"}],
            detail_sections=sections,
            evidence_status=status,
        )
    if EARBUDS_ALTERNATIVE.search(text):
        return _pack(
            "NO_MATCH",
            "I don't have enough grounded catalog evidence to name a clearly better earbud around the same price without guessing. I would keep the TOZO as the known option until we have stronger reliability evidence.",
            [],
            [{"id": "shortlist", "label": "Keep TOZO on the shortlist", "kind": "message", "message": "I'd rather keep the TOZO on my shortlist until I know more about reliability."}],
        )
    if EARBUDS_SHORTLIST.search(text):
        return _pack(
            "ACTION_RESULT",
            "That makes sense. I'll keep it as an option rather than treating it as a final recommendation.",
            [],
            [],
        )
    return None


def _exact_story_reply(
    text: str,
    *,
    action_status: dict[str, Any] | None,
    retrieved_taste: dict[str, Any] | list[str] | None,
    memory_enabled: bool,
    session_context: dict[str, Any],
    active_product_ids: set[str],
) -> dict[str, Any] | None:
    from . import products as product_service

    products = {item["id"]: item for item in product_service.get_products([KABEL_ID, BASICS_ID, DVI_ID])}
    kabel, basics, dvi = products.get(KABEL_ID), products.get(BASICS_ID), products.get(DVI_ID)
    if not kabel or not basics or not dvi:
        return None
    tv_story_context = _looks_tv_story_context(session_context, active_product_ids)

    if TV_STORY_OPEN.search(text):
        taste_blob = str(retrieved_taste or {}).lower()
        uses_taste = memory_enabled and any(token in taste_blob for token in ("avoid unused", "worth the extra", "compatibility first"))
        taste_line = " I remember you don't like paying extra for features you won't use." if uses_taste else ""
        return _pack(
            "COMPARE",
            f"For this setup, I'd choose the {_money(_price(basics))} Amazon Basics cable. It lists 4K at 60Hz, matches your TV's refresh rate, and its 10-foot length should give you enough room.{taste_line} The KabelDirekt's higher listed capability doesn't offer a clear benefit for this particular TV.",
            [_ref(basics, "primary", "10 ft · listed 4K@60Hz"), _ref(kabel, "alternative", "15 ft · listed 4K@120Hz")],
            [],
            comparison_data=_comparison(basics, kabel, [
                ("Listed video", "4K@60Hz", "4K@120Hz"),
                ("Length", "10 ft", "15 ft"),
                ("Price", _money(_price(basics)), _money(_price(kabel))),
            ]),
            decision_highlight="Amazon Basics · Best fit for this setup",
        )

    if TV_FUTURE_PROOF.search(text) and tv_story_context:
        return _pack(
            "TRADEOFF",
            "Only if you're likely to use its higher capability. For your 4K 60Hz TV, both cables have enough listed video support. Since compatibility and useful value matter here, I'd save the $2.44. I'd reconsider a higher-bandwidth cable if you later need 4K at 120Hz and your devices support it.",
            [],
            [],
        )

    if TV_RELIABILITY.search(text) and tv_story_context:
        sections, status = _review_evidence([basics], before="the required cable length and the seller's return policy")
        return _pack(
            "REVIEWS",
            "I can't confidently judge long-term reliability from the verified review evidence available for this exact Amazon Basics listing. Its listed 4K at 60Hz support fits your TV, but that does not establish durability or a dropout rate. Higher advertised video capability would not prove another cable is more reliable either.",
            [],
            [],
            detail_sections=sections,
            evidence_status=status,
        )

    if TV_FINAL_CHOICE.search(text) and tv_story_context:
        return _pack(
            "ACTION_RESULT",
            "That makes sense. The 10-foot Amazon Basics cable fits your current TV needs, while the KabelDirekt remains a candidate for the future upgrade.",
            [_ref(basics, "primary", "10 ft · listed 4K@60Hz")],
            [],
            decision_highlight="Current TV pick",
        )

    if MONITOR_DISTANCE.search(text):
        return _pack(
            "RECOMMENDATION",
            f"Then I'd start with the {_money(_price(dvi))} HDMI-to-DVI cable, assuming three feet gives you enough room to route it comfortably. It solves the connection you have today; the future 4K 120Hz upgrade is a separate purchase.",
            [_ref(dvi, "primary", "HDMI to DVI · 3 ft · 1080p")],
            [{
                "id": "cheaper-deal",
                "label": "Is the $8.55 cable a better deal?",
                "kind": "message",
                "message": "But the regular Amazon Basics HDMI cable is only $8.55. Isn't that a better deal?",
            }],
        )

    if MONITOR_CHEAPER_DEAL.search(text):
        return _pack(
            "COMPARE",
            "It's a lower-priced cable for a different connection, not a better deal for your current monitor. The regular HDMI cable cannot plug into the DVI input you need today.",
            [_ref(dvi, "primary", "HDMI to DVI · 3 ft"), _ref(basics, "alternative", "HDMI to HDMI · 10 ft")],
            [{
                "id": "upgrade-value",
                "label": "What about KabelDirekt?",
                "kind": "message",
                "message": "Okay, but what about the KabelDirekt? It's only a little more expensive. Would that be worth buying for the upgrade?",
            }],
            comparison_data=_comparison(dvi, basics, [
                ("Connection", "HDMI → DVI", "HDMI → HDMI"),
                ("Listed video", "1080p", "4K@60Hz"),
                ("Length", "3 ft", "10 ft"),
                ("Price", _money(_price(dvi)), _money(_price(basics))),
            ]),
        )

    if MONITOR_UPGRADE_VALUE.search(text):
        return _pack(
            "COMPARE",
            "Potentially, for the future upgrade. KabelDirekt lists 4K at 120Hz, while the Amazon Basics HDMI cable lists 4K at 60Hz. I would still wait until you know the future monitor and cable length, because neither HDMI cable solves today's DVI connection.",
            [_ref(basics, "alternative", "10 ft · listed 4K@60Hz"), _ref(kabel, "primary", "15 ft · listed 4K@120Hz")],
            [{
                "id": "reliability",
                "label": "Check reliability evidence",
                "kind": "message",
                "message": "Specs aren't everything. Are there complaints about black screens or connection drops with the KabelDirekt?",
            }],
            comparison_data=_comparison(basics, kabel, [
                ("Listed video", "4K@60Hz", "4K@120Hz"),
                ("Connection", "HDMI → HDMI", "HDMI → HDMI"),
                ("Length", "10 ft", "15 ft"),
                ("Price", _money(_price(basics)), _money(_price(kabel))),
            ]),
        )

    if KABEL_REVIEW.search(text):
        sections, status = _review_evidence([kabel], before="the required cable length and the seller's return policy")
        return _pack(
            "REVIEWS",
            "I can't confidently judge long-term signal stability from the reviews available for this exact listing. Its listed specifications suit the planned upgrade, but that does not prove it will be more reliable. I would want stronger evidence about black screens or dropouts before calling it the safer choice.",
            [],
            [{
                "id": "remember",
                "label": "Remember how I shop",
                "kind": "message",
                "message": "That's how I usually shop. I don't mind paying a little more when something is genuinely better, but I hate paying for features I won't use. And compatibility always comes first.",
            }],
            detail_sections=sections,
            evidence_status=status,
        )

    if MONITOR_LONG_TERM_TASTE.search(text):
        return _pack(
            "PREFERENCE_UPDATE",
            "Got it. I'll put compatibility first, value reliable performance, and only favor a more expensive option when the extra cost is meaningful. Your future 4K monitor plan will stay specific to this setup.",
            [],
            [{
                "id": "current-choice",
                "label": "Keep HDMI-to-DVI for now",
                "kind": "message",
                "message": "Let's keep the HDMI-to-DVI cable as my current choice. I'll compare the other two when I upgrade.",
            }],
        )

    if MONITOR_FINAL_CHOICE.search(text):
        return _pack(
            "ACTION_RESULT",
            "Done. The HDMI-to-DVI cable is your current choice, and the other two remain in My Picks for your future upgrade.",
            [_ref(dvi, "primary", "HDMI to DVI · 3 ft · 1080p")],
            [],
            decision_highlight="Current choice",
        )

    chinese = _chinese_story_reply(
        text,
        kabel=kabel,
        basics=basics,
        dvi=dvi,
        retrieved_taste=retrieved_taste,
        memory_enabled=memory_enabled,
        session_context=session_context,
        active_product_ids=active_product_ids,
    )
    if chinese:
        return chinese

    if GAMING_OPEN.search(text):
        delta = (_price(kabel) or 0) - (_price(basics) or 0)
        return _pack(
            "COMPARE",
            "For your current setup, both have suitable listed specs. The meaningful difference is your upgrade plan: "
            f"KabelDirekt advertises 4K at 120Hz, while the cheaper Amazon Basics lists 4K at 60Hz. It's a ${delta:.2f} difference, so I'd compare them based on whether that upgrade is likely.",
            [_ref(kabel, "primary", "15 ft · 4K@120Hz listed"), _ref(basics, "alternative", "10 ft · 4K@60Hz listed")],
            [
                {"id": "compare-details", "label": "Compare details", "kind": "quick", "action": "compare"},
                {"id": "view-products", "label": "View products", "kind": "message", "href": f"/product/{KABEL_ID}"},
            ],
            comparison_data=_comparison(kabel, basics, [
                ("Length", "15 ft", "10 ft"),
                ("Listed video", "4K@120Hz", "4K@60Hz"),
                ("Price", _money(_price(kabel)), _money(_price(basics))),
            ]),
        )

    if RELIABILITY_REVIEWS.search(text) and not MONITOR_REVIEW.search(text):
        sections, status = _review_evidence([kabel, basics], before="Confirm device support for the target refresh rate")
        return _pack(
            "REVIEWS",
            "I wouldn't assume that from the price. I'd look for reports of connection drops, connector issues, and performance at higher refresh rates. I don't have enough verified written reviews for these exact versions to establish which is more reliable. So the stronger case for KabelDirekt is its listed 120Hz capability, not proven durability.",
            [_ref(kabel, "primary", "4K@120Hz listed"), _ref(basics, "alternative", "4K@60Hz listed")],
            [{"id": "compare", "label": "Compare details", "kind": "quick", "action": "compare"}],
            detail_sections=sections,
            evidence_status=status,
        )

    if PERSONALIZED_CHOICE.search(text):
        used_taste = memory_enabled and "compatibility first" in str(retrieved_taste or {}).lower()
        prefix = "You mentioned in our earlier monitor conversation that compatibility matters more to you than small price savings. " if used_taste else "Given your planned 120Hz upgrade, "
        return _pack(
            "RECOMMENDATION",
            "I'd lean toward KabelDirekt. " + prefix +
            "Since you're considering 120Hz, I'd favor the option that explicitly lists support for that capability. It's only $2.44 more, though I'd still confirm that your future devices can actually use 120Hz before buying.",
            [_ref(kabel, "primary", "15 ft · 4K@120Hz listed")],
            [
                {"id": "save", "label": "Save to My Picks", "kind": "message", "message": "Save the KabelDirekt cable for me."},
                {"id": "compare", "label": "Compare", "kind": "quick", "action": "compare"},
            ],
            decision_highlight="PICKI'S PICK",
        )

    if STAY_60.search(text):
        return _pack(
            "RECOMMENDATION",
            "Then I'd change my recommendation to Amazon Basics. Its listed 4K@60Hz capability covers your current requirement, so the extra 120Hz support may not be worth paying for. Your actual needs should come before a general preference for future compatibility.",
            [_ref(basics, "primary", "10 ft · 4K@60Hz listed")],
            [
                {"id": "view", "label": "View product", "kind": "message", "href": f"/product/{BASICS_ID}"},
                {"id": "compare", "label": "Compare", "kind": "quick", "action": "compare"},
            ],
            decision_highlight="PICKI'S PICK",
        )

    if KEEP_KABEL.search(text):
        saved = bool((action_status or {}).get("saved"))
        return _pack(
            "ACTION_RESULT" if saved else "RECOMMENDATION",
            "I'll keep KabelDirekt as your choice for the planned upgrade. " + ("Saved to My Picks." if saved else "Save it to My Picks when you're ready."),
            [_ref(kabel, "primary", "15 ft · 4K@120Hz listed")],
            [{"id": "view-picks", "label": "View My Picks", "kind": "message", "href": "/saved"}] if saved else [
                {"id": "save", "label": "Save to My Picks", "kind": "message", "message": "Save the KabelDirekt cable for me."}
            ],
            decision_highlight="Saved to My Picks" if saved else "PICKI'S PICK",
        )

    if MONITOR_COMPARE.search(text):
        return _pack(
            "COMPARE",
            "It has a higher listed resolution, but it doesn't directly match your DVI port. For your monitor, I'd prioritize the connection you actually need rather than paying extra for 4K capability you can't use through that cable alone.",
            [_ref(dvi, "primary", "HDMI ↔ DVI · 1080p listed"), _ref(basics, "alternative", "HDMI ↔ HDMI · 4K@60Hz listed")],
            [
                {"id": "compare", "label": "Compare with Picki", "kind": "quick", "action": "compare"},
                {"id": "view-products", "label": "View products", "kind": "message", "href": f"/product/{DVI_ID}"},
            ],
            comparison_data=_comparison(dvi, basics, [
                ("Connector", "HDMI ↔ DVI", "HDMI ↔ HDMI"),
                ("Listed video", "1080p", "4K@60Hz"),
                ("Price", _money(_price(dvi)), _money(_price(basics))),
            ]),
        )

    if MONITOR_REVIEW.search(text):
        sections, status = _review_evidence([dvi], before="Check cable length and return policy")
        return _pack(
            "REVIEWS",
            "That's worth checking. The product listing gives us the connector and resolution information, but I don't have enough verified written reviews for this exact version to judge long-term reliability. I'd check the cable length and return policy before ordering.",
            [_ref(dvi, "primary", "HDMI ↔ DVI · 1080p listed")],
            [{"id": "view", "label": "View product", "kind": "message", "href": f"/product/{DVI_ID}"}],
            detail_sections=sections,
            evidence_status=status,
        )

    if MONITOR_TASTE.search(text):
        return _pack(
            "PREFERENCE_UPDATE",
            "I'll prioritize compatibility first and then look for good value among the options that fit.",
            [],
            [],
        )

    if re.search(r"save the hdmi-to-dvi cable", text, re.I):
        saved = bool((action_status or {}).get("saved"))
        return _pack(
            "ACTION_RESULT" if saved else "SAVE",
            "Saved to My Picks. You can come back to it whenever you're ready." if saved else "I couldn't save that cable yet.",
            [_ref(dvi, "primary", "HDMI ↔ DVI · 1080p listed")],
            [{"id": "view-picks", "label": "View My Picks", "kind": "message", "href": "/saved"}],
            decision_highlight="Saved to My Picks" if saved else None,
        )
    return None


def _chinese_story_reply(
    text: str,
    *,
    kabel: dict[str, Any],
    basics: dict[str, Any],
    dvi: dict[str, Any],
    retrieved_taste: dict[str, Any] | list[str] | None,
    memory_enabled: bool,
    session_context: dict[str, Any],
    active_product_ids: set[str],
) -> dict[str, Any] | None:
    if not re.search(r"[\u4e00-\u9fff]", text):
        return None
    lower = text.lower()
    demo_ids = {KABEL_ID, BASICS_ID, DVI_ID}
    ordered_context_ids = list(dict.fromkeys(str(item) for item in [
        *(session_context.get("compared_product_ids") or []),
        *(session_context.get("listed_product_ids") or []),
        *(session_context.get("shown_product_ids") or []),
        *(session_context.get("focus_product_ids") or []),
        session_context.get("focused_product_id"),
        session_context.get("decision_product_id"),
    ] if item))
    product_context = set(ordered_context_ids) or active_product_ids
    demo_context = bool(product_context) and product_context <= demo_ids
    products_by_id = {KABEL_ID: kabel, BASICS_ID: basics, DVI_ID: dvi}
    requirements = " ".join(str(item).lower() for item in (session_context.get("requirements") or []))
    if "dvi" in lower and "hdmi" in lower and ("120" in lower or "4k" in lower):
        return _pack(
            "COMPARE",
            "These are needs for two different stages. Your current monitor needs HDMI-to-DVI. A future 4K 120Hz setup needs both devices to support the required HDMI capability. An HDMI-to-DVI cable only solves today's connection, while a high-spec HDMI cable still cannot plug directly into a DVI monitor.",
            [_ref(dvi, "primary", "Today · HDMI ↔ DVI · 1080p"), _ref(kabel, "alternative", "Later · 15 ft · listed 4K@120Hz")],
            [
                {"id": "cheaper", "label": "Find a cheaper compatible option", "kind": "message", "message": "Is there a cheaper option that still works with HDMI-to-DVI?"},
                {"id": "risk", "label": "Review buying risks", "kind": "message", "message": "What buying risks should I know about? Show the review evidence."},
            ],
            comparison_data=_comparison(dvi, kabel, [
                ("Best timing", "Current monitor", "Future 4K 120Hz setup"),
                ("Connection", "HDMI ↔ DVI", "HDMI ↔ HDMI"),
                ("Listed video", "1080p", "4K@120Hz"),
                ("Price", _money(_price(dvi)), _money(_price(kabel))),
            ]),
        )
    if demo_context and re.search(r"更便宜|便宜一点|最低价格", text):
        if "dvi" not in requirements and ("120" in requirements or product_context == {KABEL_ID}):
            return _pack(
                "RECOMMENDATION",
                f"If 4K 120Hz is still required, there is no cheaper qualifying option in the current sample. {_display(basics)} costs {_money(_price(basics))}, but its listing only claims 4K@60Hz. I would keep {_display(kabel)} rather than drop a minimum performance requirement just to lower the price.",
                [_ref(kabel, "primary", "HDMI ↔ HDMI · listed 4K@120Hz")],
                [{"id": "stay-60", "label": "I only need 60Hz", "kind": "message", "message": "I will stay at 60Hz."}],
                decision_highlight="No cheaper option meets 4K 120Hz",
            )
        if "dvi" not in requirements and product_context <= {KABEL_ID, BASICS_ID}:
            return _pack(
                "RECOMMENDATION",
                f"If you only need HDMI-to-HDMI and 4K@60Hz is enough, {_display(basics)} is a valid lower-priced option at {_money(_price(basics))}. It cannot replace {_display(kabel)} if 4K 120Hz remains a requirement.",
                [_ref(basics, "primary", "HDMI ↔ HDMI · listed 4K@60Hz")],
                [{"id": "compare", "label": "Compare these products", "kind": "message", "message": "Compare these two products."}],
                decision_highlight="Lower-priced option for 4K 60Hz",
            )
        return _pack(
            "RECOMMENDATION",
            f"If the goal is still to connect the current DVI monitor, HDMI-to-DVI remains a hard requirement. Of these three products, only Amazon Basics HDMI to DVI directly matches the connector combination, at {_money(_price(dvi))}. The other two are HDMI-to-HDMI and cannot replace it just because their price or specifications look attractive.",
            [_ref(dvi, "primary", "HDMI ↔ DVI · 1080p")],
            [{"id": "risk", "label": "View review evidence", "kind": "message", "message": "What evidence-backed buying risks apply to this HDMI-to-DVI cable?"}],
            decision_highlight="Lowest-priced compatible option",
        )
    if demo_context and re.search(r"风险|评价|评论|靠谱吗|可靠", text):
        review_ids = [item for item in ordered_context_ids if item in products_by_id]
        if "dvi" in lower or "转" in text:
            review_ids = [DVI_ID]
        elif not review_ids:
            review_ids = [item for item in (KABEL_ID, BASICS_ID, DVI_ID) if item in product_context]
        products = [products_by_id[item] for item in review_ids[:3]]
        if not products:
            return None
        sections, status = _review_evidence(products, before="cable length, connector direction, and the return policy")
        refs = [_ref(item, "primary" if index == 0 else "alternative", "Catalog specifications checked") for index, item in enumerate(products)]
        return _pack(
            "REVIEWS",
            "Catalog specifications can confirm connectors and listed capability, but the available data does not establish a long-term failure rate for these exact versions. Without verified written reviews, I will not infer reliability from a rating or sales count. Check cable length, connector direction, and the return policy before ordering.",
            refs,
            [],
            detail_sections=sections,
            evidence_status=status,
        )
    if demo_context and re.search(r"比较|对比|区别", text):
        exact_ids = [item for item in ordered_context_ids if item in products_by_id]
        if len(exact_ids) < 2:
            exact_ids = [item for item in (DVI_ID, KABEL_ID, BASICS_ID) if item in product_context]
        if len(exact_ids) < 2:
            return None
        pair = [products_by_id[exact_ids[0]], products_by_id[exact_ids[1]]]
        left, right = pair
        connector = {DVI_ID: "HDMI ↔ DVI", KABEL_ID: "HDMI ↔ HDMI", BASICS_ID: "HDMI ↔ HDMI"}
        video = {DVI_ID: "1080p", KABEL_ID: "4K@120Hz", BASICS_ID: "4K@60Hz"}
        length = {DVI_ID: "3 ft", KABEL_ID: "15 ft", BASICS_ID: "10 ft"}
        rows = [
            ("Connection", connector[_id(left)], connector[_id(right)]),
            ("Listed video", video[_id(left)], video[_id(right)]),
            ("Distance", length[_id(left)], length[_id(right)]),
            ("Price", _money(_price(left)), _money(_price(right))),
        ]
        return _pack(
            "COMPARE",
            "I am comparing only the candidates you selected. The decisive difference is not which specification is highest, but whether the connector matches the actual device. Future upgrade capability should be evaluated separately from today's connection need.",
            [_ref(left, "primary", rows[0][1]), _ref(right, "alternative", rows[0][2])],
            [{"id": "risk", "label": "View review evidence", "kind": "message", "message": "Show the review evidence and unverified information in this comparison."}],
            comparison_data=_comparison(left, right, rows),
        )
    if re.search(r"以后|长期|今后", text) and re.search(r"兼容|适配", text):
        return _pack(
            "PREFERENCE_UPDATE",
            "I will add “Compatibility first” as a preference suggestion. After you confirm it, future conversations will filter out incompatible products before comparing price and performance.",
            [],
            [{"id": "taste", "label": "Review in My Taste", "kind": "message", "href": "/taste"}],
        )
    if demo_context and memory_enabled and re.search(r"按我的偏好|根据我的偏好", text) and ("compatibility" in str(retrieved_taste or {}).lower() or "兼容" in str(retrieved_taste or {})):
        return _pack(
            "RECOMMENDATION",
            "Using your confirmed “Compatibility first” preference, I will rule out connector mismatches before comparing price. For the current DVI monitor, Amazon Basics HDMI to DVI still ranks first.",
            [_ref(dvi, "primary", "HDMI ↔ DVI · 1080p")],
            [],
            decision_highlight="Confirmed preference applied",
        )
    return None


def _comparison(left: dict[str, Any], right: dict[str, Any], rows: list[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "winner_product_id": left.get("id"),
        "columns": [
            {"product_id": left.get("id"), "title": _display(left), "price": _price(left)},
            {"product_id": right.get("id"), "title": _display(right), "price": _price(right)},
        ],
        "rows": [{"label": label, "values": [left_value, right_value]} for label, left_value, right_value in rows],
    }


def _review_evidence(products: list[dict[str, Any]], *, before: str) -> tuple[list[dict[str, Any]], str]:
    from .review_provider import fetch_review_intelligence

    verified = []
    for product in products:
        intel = fetch_review_intelligence(product)
        verified.extend(item for item in (intel.get("sources") or []) if item.get("verified") is True and item.get("snippet"))
    if not verified:
        return ([{
            "id": "review-evidence",
            "title": "Review evidence",
            "collapsed": False,
            "lines": [
                "Connectors and listed capability: verified from catalog information",
                "Long-term reliability: not enough verified review evidence",
                f"Before ordering, confirm: {before}",
            ],
        }], "insufficient_reviews")
    return ([{
        "id": "review-evidence",
        "title": "Verified review evidence",
        "collapsed": False,
        "lines": [str(item["snippet"])[:180] for item in verified[:3]],
    }], "verified_reviews")


def _pack(
    reply_type: str,
    message: str,
    refs: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    *,
    comparison_data: dict[str, Any] | None = None,
    clarification_options: list[dict[str, Any]] | None = None,
    decision_highlight: str | None = None,
    detail_sections: list[dict[str, Any]] | None = None,
    evidence_status: str = "catalog",
) -> dict[str, Any]:
    return {
        "response_mode": "QUICK",
        "response_type": reply_type,
        "primary_message": message,
        "message": message,
        "key_facts": [],
        "product_refs": refs,
        "detail_sections": detail_sections or [],
        "suggested_actions": actions[:2],
        "direct_recommendation": refs[0]["title"] if refs else None,
        "product_highlights": [],
        "technical_specifications": [],
        "price_value_analysis": None,
        "customer_review_summary": None,
        "product_comparisons": (comparison_data or {}).get("summary"),
        "important_drawbacks": [],
        "suggested_follow_up_questions": [a["label"] for a in actions[:2]],
        "comparison_data": comparison_data,
        "clarification_options": clarification_options or [],
        "decision_highlight": decision_highlight,
        "evidence_status": evidence_status,
    }
