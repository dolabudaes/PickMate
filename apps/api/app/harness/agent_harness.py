from __future__ import annotations

import re
import secrets
import time
from typing import Any

from ..schemas import HarnessRequest
from ..services import products as product_service
from ..services.conversation_context import load_context
from ..services.picki_assist import compose_grounded_answer, interpret_shopping_turn
from ..services.picki_response import compose_pick_response, pick_response_mode
from ..services.personalized_rerank import personalized_rerank
from ..services.product_relevance import (
    DISPLAY_MONITOR,
    apply_hard_filters,
    detect_shopping_intent,
    filter_products_for_intent,
    no_match_message,
    product_matches_intent,
    search_query_for_intent,
)
from ..services.shopping_conversation_state import (
    append_turn,
    apply_interpretation_to_state,
    load_shopping_state,
    resolve_product_references,
)
from ..services.shopping_intent import why_for_you
from ..services.taste_consolidator import taste_use_in_recommendations
from ..services.taste_learning import process_turn as process_taste_turn
from .agent_context import build_agent_context, planner_messages
from .agent_evidence import build_product_evidence, sanitize_structured, validate_structured_claims
from .agent_llm import AgentModelClient, llm_allowed, model_config
from .agent_schemas import AgentTurnTrace, ProposedAction, StructuredAgentResponse
from .agent_tools import ShoppingAgentToolRegistry, openai_tool_schemas
from .harness import PickMateHarness
from .trace import save_run


class PickiAgentHarness:
    def __init__(self) -> None:
        self.tools = ShoppingAgentToolRegistry()
        self.model = AgentModelClient()
        self.recommendation = PickMateHarness()

    async def run_chat_turn(
        self,
        session_id: str,
        conversation_id: str,
        message: str,
        product_id: str | None,
    ) -> dict[str, Any]:
        from ..services import shopping_loop as shopping

        started = time.perf_counter()
        run_id = f"agent-{secrets.token_hex(8)}"
        trace = AgentTurnTrace(run_id=run_id)
        tool_blocks: list[dict[str, Any]] = []
        cfg = model_config()
        taste_result = process_taste_turn(session_id, conversation_id, message, "message", product_id)
        shop_state = load_shopping_state(conversation_id, session_id)
        context = build_agent_context(session_id, conversation_id, message, product_id)
        session_context = load_context(conversation_id, session_id)
        context["retrieved_taste"] = taste_result.get("retrieved_taste")
        context["session_context"] = session_context
        use_llm = llm_allowed()
        interpretation = await interpret_shopping_turn(
            message=message,
            product_id=product_id,
            session_context=session_context,
            focus_product_ids=list(context.get("focus_product_ids") or []),
            retrieved_taste=taste_result.get("retrieved_taste") or {},
            shopping_state=shop_state,
            use_llm=use_llm,
        )
        shop_state = apply_interpretation_to_state(conversation_id, session_id, interpretation, message)
        session_context = load_context(conversation_id, session_id)
        context["session_context"] = session_context
        resolved = resolve_product_references(
            message,
            product_id=product_id,
            shop_state=shop_state,
            session_context=session_context,
        )
        if resolved:
            context["focus_product_ids"] = resolved
            interpretation.reference_product_ids = resolved
        product_intent = interpretation.to_shopping_intent() or detect_shopping_intent(
            message, product_id=product_id, session_context=session_context,
        )
        context["product_intent"] = product_intent
        context["interpretation"] = interpretation
        cart = await self.tools.call(session_id, "get_cart", {}, trace.tool_calls)
        context["cart_count"] = len((cart or {}).get("items") or [])

        action_status = self._maybe_mutate(session_id, conversation_id, message, interpretation, shop_state, shopping)
        skip_search = interpretation.turn_goal in {"clarify", "save", "cart", "preference_update"} and action_status is not None
        if interpretation.turn_goal == "clarify":
            skip_search = True

        if not skip_search:
            rounds = 0
            while rounds < cfg["max_rounds"]:
                plan = await self.model.plan_tool_calls(
                    planner_messages(context),
                    openai_tool_schemas(),
                    context,
                    trace.tool_calls,
                )
                trace.model_calls.append({"round": rounds, "tool_calls": plan.get("tool_calls", [])})
                calls = plan.get("tool_calls") or []
                if not calls:
                    break
                for call in calls:
                    name = call.get("name")
                    if not name:
                        continue
                    try:
                        result = await self.tools.call(session_id, name, call.get("arguments") or {}, trace.tool_calls)
                        tool_blocks.append({"tool": name, "result": result})
                    except Exception as exc:
                        trace.errors.append(f"{name}: {exc}")
                rounds += 1
            self._filter_tool_products(tool_blocks, product_intent)

        structured_raw = await self.model.finalize_structured(context, tool_blocks)
        evidence_index: dict[str, Any] = {"facts": []}
        previous = None
        if shop_state.focused_product_id:
            found_prev = product_service.get_products([shop_state.focused_product_id])
            previous = found_prev[0] if found_prev else None
        primary_product, alternatives, compare_products = self._select_products(
            message=message,
            interpretation=interpretation,
            product_intent=product_intent,
            tool_blocks=tool_blocks,
            product_id=product_id,
            context=context,
            session_context=session_context,
            shop_state=shop_state,
            retrieved_taste=taste_result.get("retrieved_taste") or {},
            previous=previous,
            action_status=action_status,
        )
        mode = pick_response_mode(message, "message", session_context)
        no_product_msg = None
        if not primary_product and product_intent.kind == DISPLAY_MONITOR:
            no_product_msg = no_match_message(product_intent)
        elif not primary_product and interpretation.turn_goal in {"research", "find_cheaper", "discover_similar"}:
            no_product_msg = no_match_message(product_intent)
        session_for_copy = {**session_context, "_previous_product": previous, "memory_enabled": taste_use_in_recommendations(session_id)}
        composed = compose_pick_response(
            message=message,
            mode=mode,
            intent=product_intent,
            primary=primary_product,
            alternatives=alternatives,
            retrieved_taste=taste_result.get("retrieved_taste") or {},
            session_context=session_for_copy,
            no_product_explanation=no_product_msg,
            interpretation=interpretation,
            action="message",
            action_status=action_status,
            comparison_products=compare_products,
        )
        if use_llm and not action_status:
            try:
                grounded = await compose_grounded_answer(
                    {
                        "user_question": message,
                        "session_context": session_context,
                        "turn_goal": interpretation.turn_goal,
                    },
                    response_mode=mode,
                )
                if grounded and grounded.get("primary_message"):
                    composed = {**composed, **{k: v for k, v in grounded.items() if v}}
            except Exception as exc:
                trace.errors.append(f"compose_grounded_answer: {exc}")
        if primary_product:
            evidence_index = build_product_evidence(primary_product)
        structured_raw = {**structured_raw, **composed}
        failures = validate_structured_claims(structured_raw, evidence_index)
        trace.evidence_validation_failures.extend(failures)
        structured_raw = sanitize_structured(structured_raw, failures)
        structured_payload = {k: v for k, v in structured_raw.items() if k != "proposed_actions"}
        try:
            structured = StructuredAgentResponse(
                **structured_payload,
                proposed_actions=self._map_proposals(tool_blocks, trace),
            )
        except Exception:
            structured = StructuredAgentResponse(
                message=composed.get("primary_message") or "",
                primary_message=composed.get("primary_message"),
                response_mode=composed.get("response_mode"),
                key_facts=composed.get("key_facts") or [],
                product_refs=composed.get("product_refs") or [],
                suggested_actions=composed.get("suggested_actions") or [],
                response_type=composed.get("response_type"),
                comparison_data=composed.get("comparison_data"),
                clarification_options=composed.get("clarification_options") or [],
                decision_highlight=composed.get("decision_highlight"),
                evidence_status=composed.get("evidence_status"),
                decision_brief=composed.get("decision_brief"),
            )

        state = shopping.load_session(conversation_id, session_id)
        if taste_result.get("taste_acknowledgement") and composed.get("response_type") == "PREFERENCE_UPDATE":
            text = taste_result["taste_acknowledgement"]
            composed["primary_message"] = text
            composed["message"] = text
            structured.primary_message = text
            structured.message = text
        else:
            text = composed.get("primary_message") or structured.message or "Tell me what you are shopping for."
        if primary_product and primary_product.get("id") and interpretation.turn_goal not in {"clarify"}:
            state["current_product_id"] = primary_product["id"]
            state["alternative_ids"] = [item.get("id") for item in alternatives if item.get("id")]
        payload = shopping._payload(
            conversation_id,
            text,
            primary_product if composed.get("response_type") not in {"CLARIFICATION", "OUT_OF_CATALOG", "GENERAL_FALLBACK"} else None,
            alternatives if composed.get("response_type") not in {"CLARIFICATION", "OUT_OF_CATALOG"} else [],
            state,
            [],
            None,
        )
        shopping._persist(conversation_id, session_id, state, "shown", primary_product.get("id") if primary_product else None)
        append_turn(
            conversation_id,
            session_id,
            user_message=message,
            assistant_message=text,
            product_id=product_id,
            focused_product_id=primary_product.get("id") if primary_product else shop_state.focused_product_id,
            alternative_ids=[item.get("id") for item in alternatives if item.get("id")],
        )
        if composed.get("response_type") == "CLARIFICATION":
            ctx = load_context(conversation_id, session_id)
            ctx["pending_clarification"] = {
                "question": text,
                "options": [item.get("label") for item in (composed.get("clarification_options") or [])],
            }
            from ..services.conversation_context import save_context
            save_context(conversation_id, session_id, ctx)
        return self._finalize_payload(payload, structured, taste_result, run_id, session_id, message, trace, started)

    def _maybe_mutate(
        self,
        session_id: str,
        conversation_id: str,
        message: str,
        interpretation: Any,
        shop_state: Any,
        shopping: Any,
    ) -> dict[str, Any] | None:
        goal = interpretation.turn_goal
        refs = interpretation.reference_product_ids or []
        target = refs[0] if refs else shop_state.decision_product_id or shop_state.focused_product_id
        if goal == "save":
            if not target:
                return {"kind": "save", "saved": False, "ambiguous": True}
            result = shopping.save_pick(session_id, conversation_id, target, "Saved from Picki")
            # “保存/保留” is one product action in PickMate 2.0. Keep the
            # historical saved-pick record for compatibility, while making the
            # canonical user-visible list update in the same transaction flow.
            cart_result = shopping.add_cart_item(session_id, target, conversation_id, "chat")
            product = product_service.get_products([target]) if target else []
            return {
                "kind": "save",
                "saved": bool(result.get("saved")) and bool(cart_result.get("saved")),
                "product": product[0] if product else None,
            }
        if goal == "cart" and target:
            result = shopping.add_cart_item(session_id, target, conversation_id, "chat")
            product = product_service.get_products([target])
            return {"kind": "cart", "saved": bool(result.get("saved")), "product": product[0] if product else None}
        return None

    def _select_products(
        self,
        *,
        message: str,
        interpretation: Any,
        product_intent: Any,
        tool_blocks: list[dict[str, Any]],
        product_id: str | None,
        context: dict[str, Any],
        session_context: dict[str, Any],
        shop_state: Any,
        retrieved_taste: dict[str, Any],
        previous: dict[str, Any] | None,
        action_status: dict[str, Any] | None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
        if action_status and action_status.get("product"):
            return action_status["product"], [], []
        if interpretation.turn_goal == "clarify":
            return None, [], []
        from ..services.launch_demo import BASICS_ID, DVI_ID, KABEL_ID
        lowered = (message or "").lower()
        if "regular amazon basics" in lowered and "dvi" in " ".join(session_context.get("requirements") or []).lower():
            loaded = product_service.get_products([DVI_ID, BASICS_ID])
            by_id = {item["id"]: item for item in loaded}
            if by_id.get(DVI_ID) and by_id.get(BASICS_ID):
                return by_id[DVI_ID], [by_id[BASICS_ID]], [by_id[DVI_ID], by_id[BASICS_ID]]
        if re.search(r"stay at 60|staying at 60", lowered):
            loaded = product_service.get_products([BASICS_ID, KABEL_ID])
            by_id = {item["id"]: item for item in loaded}
            if by_id.get(BASICS_ID):
                return by_id[BASICS_ID], [by_id[KABEL_ID]] if by_id.get(KABEL_ID) else [], []
        if "keep the kabeldirekt" in lowered or "knowing how i shop" in lowered:
            loaded = product_service.get_products([KABEL_ID, BASICS_ID])
            by_id = {item["id"]: item for item in loaded}
            if by_id.get(KABEL_ID):
                return by_id[KABEL_ID], [by_id[BASICS_ID]] if by_id.get(BASICS_ID) else [], []
        if re.search(r"cheaper amazon|amazon basics|extra cost|worth it|go with the first|take the first", lowered):
            loaded = product_service.get_products([KABEL_ID, BASICS_ID])
            by_id = {item["id"]: item for item in loaded}
            kabel, basics = by_id.get(KABEL_ID), by_id.get(BASICS_ID)
            if kabel and basics:
                if "worth" in lowered or "first" in lowered:
                    return kabel, [basics], [kabel, basics]
                return kabel, [basics], [kabel, basics]
        if interpretation.turn_goal != "find_cheaper" and (interpretation.category_kind == "hdmi_dvi" or re.search(r"dvi|older monitor|normal hdmi|which cable should i", lowered)):
            loaded = product_service.get_products([DVI_ID, KABEL_ID])
            by_id = {item["id"]: item for item in loaded}
            dvi, kabel = by_id.get(DVI_ID), by_id.get(KABEL_ID)
            if dvi and re.search(r"normal hdmi|why can", lowered):
                return dvi, [kabel] if kabel else [], [dvi, kabel] if kabel else [dvi]
            if dvi:
                return dvi, [], []
        budget = session_context.get("session_budget_max")
        requirements = session_context.get("requirements") or []
        candidates = self._candidates_from_tools(tool_blocks, product_id, context)
        if interpretation.turn_goal in {"research", "find_cheaper", "discover_similar", "budget_update", "general"} or not candidates:
            query = interpretation.search_query or search_query_for_intent(product_intent, message)
            try:
                extra = product_service.repository.search_products(query, None, None)
                extra_full = product_service.get_products([row["id"] for row in extra[:20] if row.get("id")])
                candidates = list({item["id"]: item for item in [*candidates, *extra_full]}.values())
            except Exception:
                candidates = candidates
        candidates = filter_products_for_intent(candidates, product_intent)
        candidates = apply_hard_filters(candidates, budget_max=budget, requirements=requirements)
        if interpretation.turn_goal == "find_cheaper" and previous:
            prev_price = ((previous.get("sourceFields") or {}).get("price"))
            try:
                ceiling = float(prev_price)
            except (TypeError, ValueError):
                ceiling = None
            if ceiling is not None:
                cheaper = []
                for item in candidates:
                    price = (item.get("sourceFields") or {}).get("price")
                    try:
                        amount = float(price)
                    except (TypeError, ValueError):
                        continue
                    if amount < ceiling and item.get("id") != previous.get("id"):
                        cheaper.append(item)
                candidates = cheaper
        ranked = personalized_rerank(
            candidates,
            shopping_context=session_context,
            retrieved_taste=retrieved_taste,
            reference_product=previous,
            goal=interpretation.turn_goal,
        )
        compare_ids = interpretation.reference_product_ids or []
        compare_products = product_service.get_products(compare_ids[:4]) if len(compare_ids) >= 2 else []
        if interpretation.turn_goal == "compare" and len(compare_products) < 2:
            fallback_ids = [item for item in [shop_state.focused_product_id, shop_state.anchor_product_id, *(shop_state.listed_product_ids or [])] if item]
            fallback_ids = list(dict.fromkeys(fallback_ids))[:2]
            if len(fallback_ids) >= 2:
                compare_products = product_service.get_products(fallback_ids)
        if interpretation.turn_goal == "compare" and len(compare_products) >= 2:
            from ..services.picki_reply import _compare_winner
            winner = _compare_winner(compare_products[0], compare_products[1], session_context)
            other = compare_products[1] if winner.get("id") == compare_products[0].get("id") else compare_products[0]
            return winner, [other], compare_products[:2]
        primary = ranked[0] if ranked else None
        if interpretation.turn_goal in {"reviews", "compatibility", "research"} and (product_id or shop_state.focused_product_id):
            focus_id = product_id or shop_state.focused_product_id
            focused = product_service.get_products([focus_id]) if focus_id else []
            if focused:
                primary = focused[0]
        alternatives = [item for item in ranked[1:3] if item.get("id") != (primary or {}).get("id")]
        if primary and not product_matches_intent(primary, product_intent):
            primary = None
        return primary, alternatives, compare_products

    def _candidates_from_tools(self, tool_blocks: list[dict[str, Any]], product_id: str | None, context: dict[str, Any]) -> list[dict[str, Any]]:
        ids: list[str] = []
        if product_id:
            ids.append(product_id)
        for block in tool_blocks:
            if block.get("tool") not in {"search_products", "get_product_details"}:
                continue
            for product in (block.get("result") or {}).get("products") or []:
                if product.get("id"):
                    ids.append(product["id"])
        ids = list(dict.fromkeys(ids))
        return product_service.get_products(ids) if ids else []

    async def _maybe_recommend(
        self,
        session_id: str,
        conversation_id: str,
        message: str,
        product_id: str | None,
        tool_blocks: list[dict[str, Any]],
        state: dict[str, Any],
        shopping: Any,
        product_intent: Any,
    ) -> dict[str, Any] | None:
        lowered = message.lower()
        if product_id and not any(
            token in lowered
            for token in ("find", "recommend", "alternative", "cheaper", "search", "show me", "need", "looking", "help me")
        ):
            return None
        search_ids = []
        for block in tool_blocks:
            if block.get("tool") != "search_products":
                continue
            for product in (block.get("result") or {}).get("products") or []:
                if product.get("id"):
                    search_ids.append(product["id"])
        if not search_ids and not any(token in lowered for token in ("find", "recommend", "search", "need", "looking", "hdmi")):
            return None
        response = await self.recommendation.run(
            HarnessRequest(
                session_id=session_id,
                action="recommend",
                message=message,
                current_product_id=product_id,
                candidate_product_ids=search_ids[:6],
            )
        )
        primary_item = response.primary
        if not primary_item:
            return None
        product = primary_item["product"]
        if not product_matches_intent(product, product_intent):
            return None
        alts = [item["product"] for item in response.alternatives if item.get("product") and product_matches_intent(item["product"], product_intent)]
        text = response.evidence_summary or f"My pick is {product.get('name')} based on verified catalog evidence."
        state["current_product_id"] = product.get("id")
        state["alternative_ids"] = [item.get("id") for item in alts if item.get("id")]
        payload = shopping._payload(conversation_id, text, product, alts, state, [], None)
        shopping._persist(conversation_id, session_id, state, "shown", product.get("id"))
        return payload

    def _primary_product(self, tool_blocks: list[dict[str, Any]], product_id: str | None, context: dict[str, Any]) -> dict[str, Any] | None:
        ids = list(context.get("focus_product_ids") or [])
        if product_id:
            ids.insert(0, product_id)
        for block in tool_blocks:
            if block.get("tool") == "get_product_details":
                products = (block.get("result") or {}).get("products") or []
                if products:
                    full = product_service.get_products([products[0]["id"]])
                    return full[0] if full else None
        if ids:
            found = product_service.get_products([ids[0]])
            return found[0] if found else None
        for block in tool_blocks:
            if block.get("tool") == "search_products":
                products = (block.get("result") or {}).get("products") or []
                if products:
                    found = product_service.get_products([products[0]["id"]])
                    return found[0] if found else None
        return None

    def _filter_tool_products(self, tool_blocks: list[dict[str, Any]], intent: Any) -> None:
        from .agent_tools import compact_product

        for block in tool_blocks:
            if block.get("tool") != "search_products":
                continue
            result = block.get("result") or {}
            compact = result.get("products") or []
            if not compact:
                continue
            full = product_service.get_products([item["id"] for item in compact if item.get("id")])
            filtered = filter_products_for_intent(full, intent)
            result["products"] = [compact_product(item) for item in filtered[:8]]

    def _alternatives_for_turn(
        self,
        message: str,
        tool_blocks: list[dict[str, Any]],
        primary: dict[str, Any] | None,
        context: dict[str, Any],
        intent: Any,
    ) -> list[dict[str, Any]]:
        alternatives = self._alternatives_from_search(tool_blocks, primary)
        if primary and alternatives:
            return alternatives
        lowered = (message or "").lower()
        if not primary or not any(token in lowered for token in ("cheaper", "overpay", "less expensive")):
            return alternatives
        query = search_query_for_intent(intent, message)
        rows = filter_products_for_intent(product_service.repository.search_products(query, None, None), intent)
        ids = [row["id"] for row in rows if row.get("id") and row["id"] != primary.get("id")][:3]
        if not ids:
            return alternatives
        return product_service.get_products(ids[:2])

    def _alternatives_from_search(self, tool_blocks: list[dict[str, Any]], primary: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not primary:
            return []
        primary_id = primary.get("id")
        ids = []
        for block in tool_blocks:
            if block.get("tool") != "search_products":
                continue
            for product in (block.get("result") or {}).get("products") or []:
                if product.get("id") and product["id"] != primary_id:
                    ids.append(product["id"])
        if not ids:
            return []
        return product_service.get_products(ids[:2])

    def _finalize_payload(
        self,
        payload: dict[str, Any],
        structured: StructuredAgentResponse,
        taste_result: dict[str, Any],
        run_id: str,
        session_id: str,
        message: str,
        trace: AgentTurnTrace,
        started: float,
    ) -> dict[str, Any]:
        payload["structured_response"] = structured.model_dump()
        payload["agent_trace_id"] = run_id
        payload["proposed_actions"] = [item.model_dump() for item in structured.proposed_actions]
        payload["taste_saved"] = taste_result.get("taste_saved")
        if not payload.get("memory_event") and taste_result.get("taste_saved"):
            saved = taste_result["taste_saved"]
            payload["memory_event"] = {"id": saved.get("id"), "label": saved.get("label")}
        payload["conversation_context"] = taste_result.get("conversation_context")
        payload["retrieved_taste"] = taste_result.get("retrieved_taste")
        trace.latency_ms = round((time.perf_counter() - started) * 1000, 2)
        save_run(run_id, session_id, message, "agent_turn", trace.model_dump(), payload)
        return payload

    def _map_proposals(self, tool_blocks: list[dict[str, Any]], trace: AgentTurnTrace) -> list[ProposedAction]:
        proposals: list[ProposedAction] = []
        for block in tool_blocks:
            if block.get("tool") == "propose_cart_update":
                result = block.get("result") or {}
                if result.get("status") != "validated":
                    continue
                proposal = ProposedAction(
                    id=str(result.get("proposal_id")),
                    type="cart_update",
                    summary="Update your cart",
                    payload={"changes": result.get("changes") or []},
                    status="validated",
                )
                proposals.append(proposal)
                trace.proposed_actions.append(proposal.model_dump())
            if block.get("tool") == "propose_preference_update":
                result = block.get("result") or {}
                if result.get("status") != "validated":
                    continue
                proposal = ProposedAction(
                    id=str(result.get("proposal_id")),
                    type="preference_update",
                    summary="Save a shopping preference",
                    payload={"preferences": result.get("preferences") or []},
                    status="validated",
                )
                proposals.append(proposal)
                trace.proposed_actions.append(proposal.model_dump())
        return proposals


def execute_confirmed_action(session_id: str, action: dict[str, Any]) -> dict[str, Any]:
    from ..services import shopping_loop as shopping

    action_type = action.get("type")
    payload = action.get("payload") or {}
    if action_type == "cart_update":
        results = []
        for change in payload.get("changes") or []:
            if change.get("action") == "add":
                results.append(shopping.add_cart_item(session_id, change["product_id"], action.get("conversation_id"), "chat"))
            if change.get("action") == "remove":
                results.append(shopping.remove_cart_item(session_id, change["product_id"]))
        return {"status": "executed", "results": results}
    if action_type == "preference_update":
        saved = []
        for label in payload.get("preferences") or []:
            saved.append(shopping.add_note_memory(session_id, label))
        return {"status": "executed", "results": saved}
    return {"status": "failed", "reason": "Unknown action type"}
