from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query, Header
from typing import Dict, List, Any, Optional
from bson import ObjectId
from datetime import datetime, timezone
from ..db import get_db

router = APIRouter(prefix="/chat", tags=["chat"])

class Hub:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, room_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(room_id, []).append(ws)

    def disconnect(self, room_id: str, ws: WebSocket):
        if room_id in self.rooms and ws in self.rooms[room_id]:
            self.rooms[room_id].remove(ws)
            if not self.rooms[room_id]:
                self.rooms.pop(room_id, None)

    async def broadcast(self, room_id: str, message: dict):
        for ws in list(self.rooms.get(room_id, [])):
            try:
                await ws.send_json(message)
            except Exception:
                # drop broken
                try: self.disconnect(room_id, ws)
                except: pass

hub = Hub()

def _room_id(a: str, b: str) -> str:
    arr = sorted([a, b])
    return f"{arr[0]}_{arr[1]}"

@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, peer_id: str, db = Depends(get_db)):
    # NOTE: WebSocket headers are not auto-mapped; FastAPI exposes headers via websocket.headers
    # We expect `x-user-id` header.
    user_id = websocket.headers.get("x-user-id")
    if not user_id or not ObjectId.is_valid(user_id) or not ObjectId.is_valid(peer_id):
        await websocket.close(code=4001)
        return
    room_id = _room_id(user_id, peer_id)
    await hub.connect(room_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            content = (data.get("content") or "").strip()
            if not content:
                continue
            doc = {
                "room_id": room_id,
                "from": ObjectId(user_id),
                "to": ObjectId(peer_id),
                "content": content,
                "ts": datetime.now(timezone.utc).isoformat()
            }
            await db.messages.insert_one(doc)
            await hub.broadcast(room_id, {"room_id": room_id, "from": user_id, "to": peer_id, "content": content, "ts": doc["ts"]})
    except WebSocketDisconnect:
        hub.disconnect(room_id, websocket)

@router.get("/history")
async def history(peer_id: str, page: int = 1, limit: int = 50, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id) or not ObjectId.is_valid(peer_id):
        raise HTTPException(401, "Missing or invalid X-User-Id / peer_id")
    room_id = _room_id(x_user_id, peer_id)
    skip = max(0, (page-1)*min(limit,200))
    cur = db.messages.find({"room_id": room_id}).sort([("ts",-1)]).skip(skip).limit(min(limit,200))
    items = []
    async for m in cur:
        m["_id"] = str(m["_id"]); m["from"] = str(m["from"]); m["to"] = str(m["to"])
        items.append(m)
    total = await db.messages.count_documents({"room_id": room_id})
    return {"items": items[::-1], "page": page, "limit": min(limit,200), "total": total}
