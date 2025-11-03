from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Any, List, Optional
from math import sqrt
from bson import ObjectId
from ..db import get_db

router = APIRouter(prefix="/matching", tags=["matching"])

def _oid_ok(x: str) -> bool:
    return ObjectId.is_valid(x)

def _distance_km(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b: return None
    # very rough haversine approximation using Euclidean on lat/lng degrees scaled
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0
    lon1, lat1 = a
    lon2, lat2 = b
    dlon = radians(lon2 - lon1)
    dlat = radians(lat2 - lat1)
    aa = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    c = 2 * atan2(sqrt(aa), sqrt(1-aa))
    return R * c

def _habit_score(a: dict, b: dict) -> float:
    # simple: +1 for each exact match on boolean/string fields normalized to [0,1]
    if not a or not b: return 0.0
    keys = set(a.keys()) | set(b.keys())
    if not keys: return 0.0
    m = 0; n = 0
    for k in keys:
        va = a.get(k); vb = b.get(k)
        n += 1
        m += 1 if (va == vb) else 0
    return m / n

@router.get("/roommates")
async def match_roommates(
    top_k: int = 10,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    me = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not me: raise HTTPException(400, "You need to create your profile first")
    me_loc = (me.get("location") or {}).get("coordinates")
    me_budget = float(me.get("budget") or 0)
    me_habits = me.get("habits") or {}

    candidates = db.profiles.find({"user_id": {"$ne": ObjectId(x_user_id)}}).limit(500)
    scored: list[dict[str,Any]] = []
    async for c in candidates:
        c_loc = (c.get("location") or {}).get("coordinates")
        c_budget = float(c.get("budget") or 0)
        c_habits = c.get("habits") or {}

        # compute components
        habit = _habit_score(me_habits, c_habits)  # 0..1
        budget = 1.0 - (abs(me_budget - c_budget) / max(me_budget, c_budget, 1.0))  # 0..1
        dist_km = _distance_km(me_loc, c_loc)
        distance = 1.0 if dist_km is None else max(0.0, 1.0 - (dist_km / 10.0))  # full score if missing; else taper by 10km
        score = 0.5*habit + 0.3*budget + 0.2*distance
        c["_id"] = str(c["_id"]); c["user_id"] = str(c["user_id"])
        scored.append({"profile": c, "score": round(score, 3), "distance_km": None if dist_km is None else round(dist_km,2)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"items": scored[:max(1, min(top_k, 50))]}
