"""FastAPI application for AI Grandma."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request, UploadFile, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config_loader import load_config
from ..orchestrator import SessionState, run_pipeline
from ..logger import create_logger, EventLogger
from ..llm.client import get_llm_client

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONTRACTS_DIR = BASE_DIR / "contracts"
STATIC_DIR = BASE_DIR / "src" / "static"
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
STORE_PATH = BASE_DIR / "data" / "askama_profiles_and_records.json"

# Load config at startup
config = load_config(CONTRACTS_DIR)

# Create event logger
logger = create_logger(BASE_DIR / "data" / "logs")
logger.versions = config.versions

# Create app
app = FastAPI(
    title="AI Grandma",
    description="Singapore menstrual health triage assistant (prototype demo)",
    version="0.3.0",
)

# LLM client (DashScope / Alibaba Cloud Qwen, Singapore region); DummyLLM if no key
llm_client = get_llm_client()

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory session store (demo only)
sessions: dict[str, SessionState] = {}


def _load_store() -> dict[str, dict]:
    """Load the local demo store. It intentionally contains only user-saved data."""
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {
                "profiles": data.get("profiles", {}), "records": data.get("records", {}),
                "users": data.get("users", {}), "auth_sessions": data.get("auth_sessions", {}),
            }
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {"profiles": {}, "records": {}, "users": {}, "auth_sessions": {}}


def _save_store() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STORE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(local_store, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STORE_PATH)


local_store = _load_store()

PASSWORD_ITERATIONS = 310_000
AUTH_COOKIE = "askama_auth"


def _password_hash(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return salt, digest.hex()


def _verify_password(password: str, user: dict[str, Any]) -> bool:
    salt = user.get("password_salt", "")
    expected = user.get("password_hash", "")
    if not salt or not expected:
        return False
    _, actual = _password_hash(password, salt)
    return hmac.compare_digest(actual, expected)


def _public_user(user: dict[str, Any]) -> dict[str, str]:
    return {"id": user["id"], "username": user["username"]}


def _current_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(AUTH_COOKIE)
    session = local_store["auth_sessions"].get(token or "")
    if not session:
        return None
    return next((user for user in local_store["users"].values() if user.get("id") == session.get("user_id")), None)


def _storage_owner(request: Request, fallback: str) -> str:
    user = _current_user(request)
    return f"user:{user['id']}" if user else fallback


def _migrate_guest_data(user_id: str, guest_owner_id: str) -> bool:
    """Attach this browser's anonymous archive to a newly authenticated account."""
    if not guest_owner_id or len(guest_owner_id) > 100 or guest_owner_id.startswith("user:"):
        return False
    target = f"user:{user_id}"
    changed = False
    if guest_owner_id in local_store["profiles"]:
        local_store["profiles"].setdefault(target, local_store["profiles"][guest_owner_id])
        del local_store["profiles"][guest_owner_id]
        changed = True
    if guest_owner_id in local_store["records"]:
        local_store["records"].setdefault(target, []).extend(local_store["records"][guest_owner_id])
        del local_store["records"][guest_owner_id]
        changed = True
    return changed


def _login_response(user: dict[str, Any], guest_owner_id: str = "") -> JSONResponse:
    migrated = _migrate_guest_data(user["id"], guest_owner_id)
    token = secrets.token_urlsafe(32)
    local_store["auth_sessions"][token] = {"user_id": user["id"]}
    _save_store()
    response = JSONResponse({"user": _public_user(user), "migrated": migrated})
    response.set_cookie(AUTH_COOKIE, token, httponly=True, samesite="lax", secure=False, max_age=60 * 60 * 24 * 30)
    return response


def _profile_rows(profile: dict[str, Any]) -> list[dict[str, str]]:
    labels = {
        "last_period": "上次月经开始日期",
        "cycle_days": "平时周期天数",
        "period_days": "经期长度天数",
        "cycle_regular": "周期是否规律",
        "iud": "是否放置节育环",
        "anticoagulants": "最近是否服用抗凝药",
        "contraceptives": "最近是否服用避孕药",
    }
    return [{"label": labels[key], "value": str(value), "prov": "健康档案", "turn": ""}
            for key, value in profile.items() if key in labels and value not in (None, "")]


def get_or_create_session(session_id: str | None = None) -> SessionState:
    """Get an existing session or create a new one."""
    if session_id and session_id in sessions:
        return sessions[session_id]
    sid = session_id or str(uuid.uuid4())
    session = SessionState(session_id=sid)
    sessions[sid] = session
    return session


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main chat page."""
    session_id = request.query_params.get("sid")
    session = get_or_create_session(session_id)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "session_id": session.session_id,
            "modules": config.modules,
            "ui_language": session.ui_language,
        },
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page — questionnaire for weight presets."""
    session_id = request.query_params.get("sid")
    session = get_or_create_session(session_id)
    questionnaire = config.questionnaire
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "session_id": session.session_id,
            "questionnaire": questionnaire,
            "ui_language": session.ui_language,
        },
    )


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    llm_mode = "dashscope" if llm_client.provider == "dashscope" else "dummy"
    return {
        "status": "ok",
        "version": "0.3.0",
        "modules_loaded": config.module_ids,
        "redflag_rules": len(config.redflag_rules),
        "question_trees": len(config.question_trees),
        "decision_tables": len(config.decision_tables),
        "selfcare_cards": len(config.selfcare_cards),
        "facilities": len(config.facilities),
        "llm": {
            "provider": llm_client.provider,
            "mode": llm_mode,
            "model": getattr(llm_client, "model", None),
            "base_url": getattr(llm_client, "base_url", None),
            "intake_enabled": os.getenv("LLM_INTAKE_ENABLED", "1") != "0",
        },
    }


@app.post("/api/chat")
async def chat(
    message: str = Form(""),
    session_id: str = Form(None),
    is_answer: bool = Form(False),
    answer_value: str = Form(None),
    answer_value_int: int = Form(None),
    language: str = Form("en"),
):
    """Main chat endpoint."""
    session = get_or_create_session(session_id)
    session.ui_language = language

    # Resolve answer value (can be string or int)
    actual_value = answer_value_int if answer_value_int is not None and is_answer else answer_value

    response = run_pipeline(
        user_text=message,
        session=session,
        config=config,
        is_answer=is_answer,
        answer_value=actual_value,
        logger=logger,
        turn_id=len(session.asked_question_ids),
        llm=llm_client,
        llm_intake_enabled=os.getenv("LLM_INTAKE_ENABLED", "1") != "0",
    )

    return JSONResponse({
        "session_id": session.session_id,
        "response": response,
        "session_state": session.to_dict(),
    })


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session state."""
    if session_id not in sessions:
        return JSONResponse({"error": "session not found"}, status_code=404)
    return sessions[session_id].to_dict()


@app.post("/api/sessions/new")
async def create_new_session(language: str = Form("en")):
    """Create a new session."""
    session = get_or_create_session()
    session.ui_language = language
    return {"session_id": session.session_id}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = _current_user(request)
    return {"user": _public_user(user) if user else None}


@app.post("/api/auth/register")
async def auth_register(request: Request, payload: dict[str, Any] = Body(...)):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    key = username.casefold()
    if not (2 <= len(username) <= 30) or any(char.isspace() for char in username):
        return JSONResponse({"error": "用户名请使用 2–30 个不含空格的字符。"}, status_code=400)
    if not (6 <= len(password) <= 128):
        return JSONResponse({"error": "密码请使用 6–128 个字符。"}, status_code=400)
    if key in local_store["users"]:
        return JSONResponse({"error": "这个用户名已被使用，请直接登录。"}, status_code=409)
    salt, password_hash = _password_hash(password)
    user = {"id": str(uuid.uuid4()), "username": username, "password_salt": salt, "password_hash": password_hash}
    local_store["users"][key] = user
    return _login_response(user, str(payload.get("guest_owner_id", "")))


@app.post("/api/auth/login")
async def auth_login(payload: dict[str, Any] = Body(...)):
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = local_store["users"].get(username.casefold())
    if not user or not _verify_password(password, user):
        return JSONResponse({"error": "用户名或密码不正确。"}, status_code=401)
    return _login_response(user, str(payload.get("guest_owner_id", "")))


@app.post("/api/auth/logout")
async def auth_logout(request: Request):
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        local_store["auth_sessions"].pop(token, None)
        _save_store()
    response = JSONResponse({"ok": True})
    response.delete_cookie(AUTH_COOKIE)
    return response


@app.get("/api/profile/{session_id}")
async def get_profile(request: Request, session_id: str):
    """Return the locally saved cycle details for this demo session."""
    return {"profile": local_store["profiles"].get(_storage_owner(request, session_id), {})}


@app.put("/api/profile/{session_id}")
async def save_profile(request: Request, session_id: str, profile: dict[str, Any] = Body(...)):
    """Save only the explicit cycle fields shown in the health-record form."""
    allowed = {
        "nickname", "last_period", "cycle_days", "period_days", "cycle_regular",
        "iud", "anticoagulants", "contraceptives",
    }
    cleaned = {key: value for key, value in profile.items() if key in allowed and value not in (None, "")}
    local_store["profiles"][_storage_owner(request, session_id)] = cleaned
    _save_store()
    return {"profile": cleaned}


@app.get("/api/records/{session_id}")
async def get_records(request: Request, session_id: str):
    records = local_store["records"].get(_storage_owner(request, session_id), [])
    return {"records": list(reversed(records))}


@app.post("/api/records")
async def save_record(request: Request, payload: dict[str, Any] = Body(...)):
    """Persist a compact consultation summary after the triage flow completes."""
    session_id = _storage_owner(request, str(payload.get("session_id", "")))
    if not session_id:
        return JSONResponse({"error": "session_id is required"}, status_code=400)
    record = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        "module": str(payload.get("module", "未说明")),
        "complaint": str(payload.get("complaint", ""))[:500],
        "level": str(payload.get("level", "未说明")),
        "summary": str(payload.get("summary", ""))[:4000],
        "dialogue": [
            {"role": str(item.get("role", "对话"))[:40], "text": str(item.get("text", ""))[:1200]}
            for item in payload.get("dialogue", []) if isinstance(item, dict)
        ][:100],
        "consultation_session_id": str(payload.get("consultation_session_id", ""))[:100],
        "language": str(payload.get("language", "zh")),
    }
    local_store["records"].setdefault(session_id, []).append(record)
    _save_store()
    return {"record": record}


@app.get("/summary/{record_id}", response_class=HTMLResponse)
async def summary_page(request: Request, record_id: str):
    """Printable consultation summary using the supplied AskaMa template."""
    match = next(
        ((owner, item) for owner, entries in local_store["records"].items() for item in entries if item.get("id") == record_id),
        None,
    )
    if not match:
        return HTMLResponse("记录不存在或已被删除。", status_code=404)
    session_id, record = match
    user = _current_user(request)
    if session_id.startswith("user:") and (not user or session_id != f"user:{user['id']}"):
        return HTMLResponse("请登录对应账号后查看这份报告。", status_code=403)
    profile = local_store["profiles"].get(session_id, {})
    # A report is a communication aid, not a re-interpretation of the medical
    # conversation.  Keep the patient's own words separate from the assistant
    # turns, and translate only the already-computed triage level for display.
    complaint = record.get("complaint") or record["module"]
    dialogue = record.get("dialogue", [])
    # Older demo records may contain prototype facility names and addresses in
    # assistant turns.  They are not verified care locations, so keep the
    # conversational record but replace that directory with a safe note.
    facility_markers = ("🏥", "📍", "Bukit Merah Polyclinic", "Queenstown Polyclinic", "Ang Mo Kio GP", "KK Hospital")
    safe_details = []
    for item in dialogue:
        clean_item = dict(item)
        text = str(clean_item.get("text", ""))
        if str(clean_item.get("role", "")).strip() in {"阿嬷", "assistant", "Assistant"} and any(marker in text for marker in facility_markers):
            clean_item["text"] = "阿嬷已给出就医建议。原型中的示例机构目录不作为实际地点提供，请使用结果页的地图入口查找附近合适的医疗服务。"
        safe_details.append(clean_item)
    def fact_label(question: str) -> str:
        """Turn a conversational question into a clinician-readable field name."""
        labels = (
            (("出血量和平时", "出血多不多"), "出血量与平时相比"),
            (("出血到目前", "出血持续"), "出血持续时间"),
            (("异常出血",), "异常出血"),
            (("异常分泌物", "异味"), "分泌物／异味"),
            (("0 到 10", "疼痛有多严重"), "疼痛程度"),
            (("疼痛主要在哪", "痛哪里"), "疼痛位置"),
            (("怎样的疼", "疼法"), "疼痛性质"),
            (("疼痛持续多长",), "疼痛持续时间"),
            (("和平时比",), "与平时相比"),
            (("突然发作", "慢慢加重"), "起病方式"),
            (("影响到日常",), "对日常活动的影响"),
            (("头晕", "晕倒"), "头晕／晕倒"),
            (("发烧", "体温"), "发热"),
            (("心跳加速", "气短"), "心悸／气短"),
            (("呕吐", "喝不进水"), "呕吐／饮水困难"),
            (("性生活",), "近期性生活"),
            (("怀孕",), "怀孕可能"),
            (("上次月经",), "上次月经"),
            (("诱发行为", "诱因"), "可能诱因"),
        )
        for hints, label in labels:
            if any(hint in question for hint in hints):
                return label
        return "补充说明"

    confirmed_facts = []
    pending_question = ""
    first_user_statement = True
    for item in dialogue:
        role = str(item.get("role", "")).strip()
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if role in {"阿嬷", "assistant", "Assistant"}:
            pending_question = text
            continue
        if role in {"我", "用户", "user", "User"}:
            # The first statement is already shown as the chief complaint.
            if first_user_statement and text == complaint.strip():
                first_user_statement = False
                continue
            first_user_statement = False
            confirmed_facts.append({"label": fact_label(pending_question), "value": text})
            pending_question = ""
    triage_labels = {
        "EMERGENCY_NOW": {
            "tag": "紧急",
            "title": "请立即前往急诊",
            "note": "建议尽快由急诊医疗团队评估；如无法安全前往，请拨打 995。",
            "tone": "emergency",
        },
        "SEE_DOCTOR_24_48H": {
            "tag": "尽快就医",
            "title": "建议在 24–48 小时内就医",
            "note": "建议尽快安排医疗评估，并携带本页向医生说明情况。",
            "tone": "soon",
        },
        "BOOK_SOON": {
            "tag": "近期就医",
            "title": "建议近期预约门诊",
            "note": "建议安排门诊评估；如症状加重或出现新的危险信号，请尽快就医。",
            "tone": "book",
        },
        "SELF_CARE": {
            "tag": "居家观察",
            "title": "可先居家观察",
            "note": "请按照本次建议观察变化；若症状加重或感到不安，请及时就医。",
            "tone": "care",
        },
    }
    triage = triage_labels.get(record["level"], {
        "tag": "分诊建议", "title": "请参考本次分诊建议",
        "note": "如症状变化或感到不安，请及时寻求医疗帮助。", "tone": "book",
    })
    # Do not repeat the prototype's example facility directory in patient
    # reports.  Locations are selected at viewing time through Maps instead.
    safe_advice = {
        "EMERGENCY_NOW": "分诊建议：请立即前往急诊；如无法安全前往，请拨打 995。",
        "SEE_DOCTOR_24_48H": "分诊建议：建议在 24–48 小时内到妇科或医院门诊评估；如症状加重，请立即去急诊。",
        "BOOK_SOON": "分诊建议：建议近期预约 GP 或 Polyclinic；如症状加重，请提前就医。",
        "SELF_CARE": "分诊建议：可先居家观察并按护理指引休息；如出现新的危险信号，请及时就医。",
    }.get(record["level"], record["summary"])
    legacy_tx = {
        "title": "问诊摘要", "generated": "生成时间", "session": "会话", "no_dx": "本摘要仅供就医沟通参考，不提供诊断。",
        "S": "主诉", "complaint": "本次模块", "B": "健康档案", "A": "问诊信息", "present": "已记录", "denied": "未记录",
        "R": "规则与不确定性", "uncertain": "未确认项目", "not_asked": "未追问项目", "guidance": "分诊建议",
        "level": "建议级别", "escalation": "需要升级就医的情况", "none": "无", "own_words": "对话摘要", "emergency": "紧急提醒", "qr": "AskaMa\n问诊摘要",
    }
    summary = {
        "generated": record["created_at"], "session_id": session_id[:8],
        "complaint": complaint,
        "details": safe_details,
        "confirmed_facts": confirmed_facts,
        "triage": triage,
        "level": record["level"], "advice": safe_advice,
        "background": _profile_rows(profile),
        # Retained only to keep the hidden legacy template markup renderable.
        "tx": legacy_tx, "lang": "zh", "emergency_box": None,
        "situation": {"complaint": complaint, "rows": [], "own_words": []},
        "present": [], "denied": [], "uncertain": [], "not_asked": [],
        "guidance": {"level": record["level"], "core": safe_advice, "escalation": []},
        "rule_ids": [], "config_versions": config.versions, "footer": "请将本页作为和医生沟通的辅助信息。",
    }
    return templates.TemplateResponse(request, "summary.html", {"s": summary})


@app.get("/api/config")
async def get_config():
    """Get loaded config info."""
    return {
        "versions": config.versions,
        "modules": config.module_ids,
        "redflag_count": len(config.redflag_rules),
        "facilities": [
            {"facility_id": f.get("facility_id"), "name": f.get("name"), "type": f.get("type")}
            for f in config.facilities
        ],
    }
