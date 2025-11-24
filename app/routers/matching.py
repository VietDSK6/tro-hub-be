from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Any, List, Optional
from math import sqrt
from bson import ObjectId
from ..db import get_db
from ..schemas import ProfilePreviewOut

router = APIRouter(prefix="/matching", tags=["matching"])

def _oid_ok(x: str) -> bool:
    return ObjectId.is_valid(x)

def _distance_km(a: list[float] | None, b: list[float] | None) -> float | None:
    if not a or not b: return None
    
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
    """Match roommates based on budget, habits, and location"""
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    me = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not me: raise HTTPException(400, "Bạn cần tạo hồ sơ của mình trước")
    me_loc = (me.get("location") or {}).get("coordinates")
    me_budget = float(me.get("budget") or 0)
    me_habits = me.get("habits") or {}

    candidates = db.profiles.find({"user_id": {"$ne": ObjectId(x_user_id)}}).limit(500)
    scored: list[dict[str,Any]] = []
    async for c in candidates:
        c_loc = (c.get("location") or {}).get("coordinates")
        c_budget = float(c.get("budget") or 0)
        c_habits = c.get("habits") or {}

        
        habit = _habit_score(me_habits, c_habits)  
        budget = 1.0 - (abs(me_budget - c_budget) / max(me_budget, c_budget, 1.0))  
        dist_km = _distance_km(me_loc, c_loc)
        distance = 1.0 if dist_km is None else max(0.0, 1.0 - (dist_km / 10.0))  
        score = 0.5*habit + 0.3*budget + 0.2*distance
        
        # Fetch user info for full name
        user = await db.users.find_one({"_id": c["user_id"]})
        full_name = user.get("name", "") if user else ""
        
        profile_dto = ProfilePreviewOut(
            _id=str(c["_id"]),
            user_id=str(c["user_id"]),
            bio=c.get("bio", ""),
            budget=c.get("budget", 0),
            desiredAreas=c.get("desiredAreas", []),
            habits=c.get("habits", {}),
            gender=c.get("gender"),
            age=c.get("age"),
            location=c.get("location"),
            full_name=full_name
        )
        
        scored.append({
            "profile": profile_dto.model_dump(by_alias=True),
            "score": round(score, 3),
            "distance_km": None if dist_km is None else round(dist_km, 2)
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"items": scored[:max(1, min(top_k, 50))]}
