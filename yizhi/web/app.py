"""FastAPI app for the yizhi web panel: SSR pages + JSON API + SSE tail.

The panel is an observation surface with exactly one write: POST an approval
verb, which appends to the channel inbox file for the will loop to poll. There
is deliberately no endpoint that starts a run, edits config, or touches the
event store — the will initiates its own runs; the panel watches and answers.

SSE design: connect → one full `state` snapshot, then a poll loop over the
events table rowid cursor emits `semantic_event` per new event plus a refreshed
`state`. Event names follow the AG-UI style (state snapshot/delta over SSE) so a
protocol adapter can be layered on later without reshaping the stream.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from yizhi.channels.base import InboundVerb
from yizhi.core.schemas import EventType, YizhiModel
from yizhi.engine.llm import load_llm
from yizhi.liaison.agent import LiaisonAgent
from yizhi.liaison.schemas import LiaisonMessage, LiaisonPendingAction
from yizhi.liaison.store import LiaisonStore, default_liaison_db_path
from yizhi.liaison.tools import LiaisonTools
from yizhi.web.data import (
    append_inbox,
    budget_series,
    fetch_events,
    latest_state,
    load_packet,
    max_event_rowid,
    read_inbox_lines,
    read_outbox_lines,
)
from yizhi.web.projections import (
    NowView,
    budget_svg_points,
    project_approvals,
    project_chat,
    project_unified_chat,
    project_now,
    project_task_history,
)

_WEB_DIR = Path(__file__).parent
DEFAULT_EVENT_LIMIT = 100


class ApprovalDecision(YizhiModel):
    verb: Literal["approve", "kill"]


class ChatInput(YizhiModel):
    """One human message from the conversation page. `kill` is accepted only as
    the explicit goal veto (text == "goal") — proposal-level kills belong to the
    approvals page, where the correlation id is verified against a real request."""

    verb: Literal["auto", "note", "ask", "vision", "kill"] = "auto"
    text: str = ""


def _event_summary(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)[:200]
    keys = ("verdict", "title", "status", "summary", "reason", "decision", "balance", "subject")
    parts = [f"{key}={payload[key]}" for key in keys if key in payload]
    return "; ".join(str(p) for p in parts)[:200] if parts else json.dumps(payload, ensure_ascii=False)[:200]


def _event_wire(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": event.get("ts", ""),
        "type": event.get("type", ""),
        "aggregate_type": event.get("aggregate_type", ""),
        "aggregate_id": event.get("aggregate_id", ""),
        "correlation_id": event.get("correlation_id") or "",
        "summary": _event_summary(event.get("payload")),
    }


def _sse(event_name: str, data: str) -> str:
    return f"event: {event_name}\ndata: {data}\n\n"


def create_app(
    db_path: str | Path,
    channel_root: str | Path,
    liaison_db_path: str | Path | None = None,
    packet_path: str | Path = Path("data/funding/promotion_packet.json"),
    poll_interval: float = 1.0,
) -> FastAPI:
    app = FastAPI(title="yizhi panel", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=_WEB_DIR / "templates")
    liaison_store = LiaisonStore(liaison_db_path or default_liaison_db_path(db_path))
    liaison_tools = LiaisonTools(db_path=db_path, channel_root=channel_root, packet_path=packet_path)
    liaison_agent = LiaisonAgent(liaison_tools, liaison_store, llm=load_llm())

    def build_now_view() -> NowView:
        intention_events = fetch_events(
            db_path, event_type=EventType.INTENTION_ACTIVATED.value, newest_first=True, limit=1
        )
        return project_now(latest_state(db_path), list(reversed(intention_events)))

    def build_tasks() -> list[dict[str, Any]]:
        events = fetch_events(db_path)
        return [t.model_dump() for t in project_task_history(events, latest_state(db_path))]

    def build_approvals() -> list[dict[str, Any]]:
        events = fetch_events(db_path)
        inbox = read_inbox_lines(channel_root)
        return [a.model_dump() for a in project_approvals(events, inbox)]

    def build_chat(limit: int = 150) -> list[dict[str, Any]]:
        messages = project_unified_chat(
            read_inbox_lines(channel_root),
            read_outbox_lines(channel_root),
            liaison_store.list_messages(limit=limit),
            limit=limit,
        )
        return [m.model_dump() for m in messages]

    def _record_explicit_chat(verb: str, text: str) -> dict[str, Any]:
        liaison_store.append(LiaisonMessage(source="human", label=verb, text=text))
        if verb in {"note", "ask"}:
            command = liaison_tools.send_to_will(verb, text)
            reply = liaison_store.append(LiaisonMessage(
                source="liaison",
                label="submitted",
                text=(
                    "已作为 ask 提交给 will；下一回路消化后，will 的回复会回到这里。"
                    if verb == "ask"
                    else "已作为 note 提交给 will；它会在下一回路作为高显著性观察被消化。"
                ),
                refs=[command.id],
            ))
            return {"ok": True, "command_id": command.id, "messages": [reply.model_dump()]}
        if verb == "vision":
            pending = LiaisonPendingAction(
                verb="vision",
                text=text,
                risk="high",
                confirmation_prompt="这会改变 will 的战略层 vision。确认后才会提交给 will。",
            )
            reply = liaison_store.append(LiaisonMessage(
                source="liaison", label="confirm", text=pending.confirmation_prompt, pending_action=pending
            ))
            return {"ok": True, "pending_action": pending.model_dump(), "messages": [reply.model_dump()]}
        if verb == "kill":
            if text.lower() not in {"goal", "当前目标"}:
                raise HTTPException(status_code=422, detail="chat kill only accepts the goal veto (text='goal')")
            pending = LiaisonPendingAction(
                verb="kill",
                text="goal",
                risk="high",
                confirmation_prompt="这会放弃当前 PURSUING 目标。确认后下一回路会重新生成目标。",
            )
            reply = liaison_store.append(LiaisonMessage(
                source="liaison", label="confirm", text=pending.confirmation_prompt, pending_action=pending
            ))
            return {"ok": True, "pending_action": pending.model_dump(), "messages": [reply.model_dump()]}
        raise HTTPException(status_code=422, detail="unsupported chat verb")

    # --- SSR pages ---

    @app.get("/")
    def page_now(request: Request):
        return templates.TemplateResponse(request, "now.html", {"page": "now", "now": build_now_view()})

    @app.get("/timeline")
    def page_timeline(request: Request, type: str | None = None, limit: int = DEFAULT_EVENT_LIMIT):
        events = [_event_wire(e) for e in fetch_events(db_path, event_type=type or None, limit=limit, newest_first=True)]
        return templates.TemplateResponse(
            request,
            "timeline.html",
            {
                "page": "timeline",
                "events": events,
                "selected_type": type or "",
                "event_types": [t.value for t in EventType],
            },
        )

    @app.get("/tasks")
    def page_tasks(request: Request):
        return templates.TemplateResponse(request, "tasks.html", {"page": "tasks", "tasks": build_tasks()})

    @app.get("/deliverables")
    def page_deliverables(request: Request):
        packet = load_packet(packet_path)
        judgments = [
            _event_wire(e)
            for e in fetch_events(db_path, event_type=EventType.JUDGMENT_RENDERED.value, newest_first=True, limit=50)
        ]
        series = budget_series(db_path)
        return templates.TemplateResponse(
            request,
            "deliverables.html",
            {
                "page": "deliverables",
                "packet": packet,
                "judgments": judgments,
                "budget_points": budget_svg_points(series),
                "budget_series_len": len(series),
            },
        )

    @app.get("/approvals")
    def page_approvals(request: Request):
        return templates.TemplateResponse(
            request, "approvals.html", {"page": "approvals", "approvals": build_approvals()}
        )

    @app.get("/chat")
    def page_chat(request: Request):
        messages = build_chat()
        return templates.TemplateResponse(
            request, "conversation.html", {"page": "chat", "messages": messages}
        )

    # --- JSON API ---

    @app.get("/api/state")
    def api_state():
        return build_now_view().model_dump()

    @app.get("/api/tasks")
    def api_tasks():
        return build_tasks()

    @app.get("/api/events")
    def api_events(type: str | None = None, limit: int = DEFAULT_EVENT_LIMIT):
        return [_event_wire(e) for e in fetch_events(db_path, event_type=type or None, limit=limit, newest_first=True)]

    @app.get("/api/approvals")
    def api_approvals():
        return build_approvals()

    @app.get("/api/deliverables")
    def api_deliverables():
        return {"packet": load_packet(packet_path), "budget_series": budget_series(db_path)}

    @app.post("/api/approvals/{correlation_id}")
    def api_decide(correlation_id: str, decision: ApprovalDecision):
        known = {a["correlation_id"] for a in build_approvals()}
        if correlation_id not in known:
            raise HTTPException(status_code=404, detail="no approval request with this correlation id")
        command = append_inbox(channel_root, InboundVerb(decision.verb), correlation_id)
        return {"ok": True, "status": "submitted", "command_id": command.id}

    @app.get("/api/chat")
    def api_chat(limit: int = 150):
        return build_chat(limit=limit)

    @app.post("/api/chat")
    def api_chat_send(message: ChatInput):
        text = message.text.strip()
        if message.verb != "kill" and not text:
            raise HTTPException(status_code=422, detail="empty message")
        if message.verb != "auto":
            return _record_explicit_chat(message.verb, text or "goal")
        result = liaison_agent.handle_user_message(text)
        return result.model_dump()

    @app.post("/api/chat/confirm/{action_id}")
    def api_chat_confirm(action_id: str):
        result = liaison_agent.confirm_pending(action_id)
        return result.model_dump()

    # --- SSE ---

    async def stream(max_cycles: int | None) -> AsyncIterator[str]:
        yield _sse("state", build_now_view().model_dump_json())
        cursor = max_event_rowid(db_path)
        cycles = 0
        while max_cycles is None or cycles < max_cycles:
            await asyncio.sleep(poll_interval)
            fresh = fetch_events(db_path, after_rowid=cursor)
            if fresh:
                cursor = max(int(e["rowid"]) for e in fresh)
                for event in fresh:
                    yield _sse("semantic_event", json.dumps(_event_wire(event), ensure_ascii=False))
                yield _sse("state", build_now_view().model_dump_json())
            cycles += 1

    @app.get("/stream")
    def sse_stream(max_cycles: int | None = None):
        return StreamingResponse(
            stream(max_cycles),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app
