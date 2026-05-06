import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

try:
    from db.mongo_adapters import _get_db_main_async, mongo_enabled
except ImportError:
    _get_db_main_async = None
    mongo_enabled = lambda: False


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["Global Chat"])

CHAT_COLLECTION = "global_chat_messages"
CHAT_STORE = Path("data/global_chat_messages.json")
CHAT_UPLOAD_DIR = Path("data/uploads/chat")
MAX_MESSAGE_LENGTH = 1500
MAX_NAME_LENGTH = 32
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = {
    ".apng",
    ".csv",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".txt",
    ".webp",
    ".zip",
}


class ChatAttachment(BaseModel):
    name: str = Field(default="file", max_length=120)
    url: str = Field(..., max_length=500)
    type: Optional[str] = Field(default=None, max_length=120)
    size: Optional[int] = Field(default=None, ge=0, le=MAX_UPLOAD_BYTES)


class ChatMessageCreate(BaseModel):
    content: str = Field(default="", max_length=MAX_MESSAGE_LENGTH)
    display_name: Optional[str] = Field(default=None, max_length=MAX_NAME_LENGTH)
    guest_id: Optional[str] = Field(default=None, max_length=80)
    timezone: Optional[str] = Field(default=None, max_length=80)
    client_time: Optional[str] = Field(default=None, max_length=80)
    attachments: List[ChatAttachment] = Field(default_factory=list)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1200)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_text(value: str, max_length: int) -> str:
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value or "")
    return cleaned.strip()[:max_length]


def _clean_name(value: Optional[str], fallback: str = "Guest Player") -> str:
    cleaned = _clean_text(value or "", MAX_NAME_LENGTH)
    return cleaned or fallback


def _public_message(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id") or doc.get("id") or ""),
        "content": doc.get("content", ""),
        "author": doc.get("author", {}),
        "attachments": doc.get("attachments", []),
        "created_at": doc.get("created_at"),
        "timezone": doc.get("timezone"),
        "client_time": doc.get("client_time"),
        "source": doc.get("source", "guest"),
    }


async def _get_collection():
    if not mongo_enabled() or _get_db_main_async is None:
        return None
    try:
        db = await _get_db_main_async()
        return db[CHAT_COLLECTION]
    except Exception as exc:
        logger.warning("Global chat MongoDB unavailable, using JSON fallback: %s", exc)
        return None


def _read_fallback_messages() -> List[Dict[str, Any]]:
    if not CHAT_STORE.exists():
        return []
    try:
        return json.loads(CHAT_STORE.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to read global chat fallback store: %s", exc)
        return []


def _write_fallback_messages(messages: List[Dict[str, Any]]) -> None:
    CHAT_STORE.parent.mkdir(parents=True, exist_ok=True)
    CHAT_STORE.write_text(json.dumps(messages[-500:], ensure_ascii=False, indent=2), encoding="utf-8")


async def _resolve_discord_user(auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
    if not auth_header:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(
                "https://discord.com/api/users/@me",
                headers={"Authorization": auth_header},
            )
        if response.status_code != 200:
            return None
        user = response.json()
        avatar_hash = user.get("avatar")
        avatar_url = None
        if avatar_hash:
            avatar_url = f"https://cdn.discordapp.com/avatars/{user.get('id')}/{avatar_hash}.png?size=96"
        return {
            "id": str(user.get("id")),
            "name": _clean_name(user.get("global_name") or user.get("username"), "Discord Player"),
            "username": _clean_name(user.get("username"), "discord"),
            "avatar_url": avatar_url,
            "kind": "discord",
        }
    except Exception as exc:
        logger.warning("Failed to resolve Discord user for chat: %s", exc)
        return None


@router.get("/messages")
async def list_messages(limit: int = 80):
    safe_limit = min(max(int(limit or 80), 1), 100)
    collection = await _get_collection()
    if collection is not None:
        cursor = collection.find({}).sort("created_at", -1).limit(safe_limit)
        docs = await cursor.to_list(length=safe_limit)
        docs.reverse()
        return {"messages": [_public_message(doc) for doc in docs]}

    messages = _read_fallback_messages()[-safe_limit:]
    return {"messages": [_public_message(doc) for doc in messages]}


@router.post("/messages", status_code=201)
async def create_message(payload: ChatMessageCreate, request: Request):
    content = _clean_text(payload.content, MAX_MESSAGE_LENGTH)
    attachments = [
        item.dict()
        for item in payload.attachments[:4]
        if item.url.startswith("/api/static/chat/")
    ]
    if not content and not attachments:
        raise HTTPException(status_code=400, detail="Message text or a file is required.")

    auth_header = request.headers.get("Authorization")
    discord_user = await _resolve_discord_user(auth_header)
    if discord_user:
        author = discord_user
        source = "discord"
    else:
        guest_id = _clean_text(payload.guest_id or "", 80) or f"guest-{uuid.uuid4().hex[:12]}"
        author = {
            "id": guest_id,
            "name": _clean_name(payload.display_name),
            "username": _clean_name(payload.display_name),
            "avatar_url": None,
            "kind": "guest",
        }
        source = "guest"

    doc = {
        "_id": uuid.uuid4().hex,
        "content": content,
        "author": author,
        "attachments": attachments,
        "timezone": _clean_text(payload.timezone or "", 80),
        "client_time": _clean_text(payload.client_time or "", 80),
        "created_at": _utc_now_iso(),
        "source": source,
        "ip_hint": request.client.host if request.client else None,
    }

    collection = await _get_collection()
    if collection is not None:
        await collection.insert_one(doc)
        excess_count = await collection.count_documents({})
        if excess_count > 500:
            old_cursor = collection.find({}, {"_id": 1}).sort("created_at", 1).limit(excess_count - 500)
            old_docs = await old_cursor.to_list(length=excess_count - 500)
            old_ids = [item["_id"] for item in old_docs]
            if old_ids:
                await collection.delete_many({"_id": {"$in": old_ids}})
    else:
        messages = _read_fallback_messages()
        messages.append(doc)
        _write_fallback_messages(messages)

    return {"message": _public_message(doc)}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 8 MB.")

    original = Path(file.filename).name
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail="This file type is not allowed.")

    CHAT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    path = CHAT_UPLOAD_DIR / stored_name
    path.write_bytes(content)

    return {
        "attachment": {
            "name": original[:120],
            "url": f"/api/static/chat/{stored_name}",
            "type": file.content_type,
            "size": len(content),
        }
    }


@router.post("/translate")
async def translate_to_english(payload: TranslateRequest):
    api_key = os.getenv("DEEPL_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Translation is not configured.")

    endpoint = os.getenv("DEEPL_API_URL")
    if not endpoint:
        endpoint = "https://api-free.deepl.com/v2/translate" if api_key.endswith(":fx") else "https://api.deepl.com/v2/translate"

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(
                endpoint,
                data={
                    "auth_key": api_key,
                    "text": payload.text,
                    "target_lang": "EN-US",
                },
            )
        if response.status_code >= 400:
            logger.warning("DeepL translation failed: %s %s", response.status_code, response.text[:200])
            raise HTTPException(status_code=502, detail="Translation provider failed.")
        data = response.json()
        item = (data.get("translations") or [{}])[0]
        return {
            "translated_text": item.get("text", payload.text),
            "detected_source_lang": item.get("detected_source_language"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Global chat translation error: %s", exc)
        raise HTTPException(status_code=502, detail="Translation failed.")
