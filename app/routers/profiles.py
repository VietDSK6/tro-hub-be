from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Optional, Any, List
from bson import ObjectId
from ..db import get_db

router = APIRouter(prefix="/profiles", tags=["profiles"])

def _oid(x: str) -> ObjectId:
    if not ObjectId.is_valid(x):
        raise HTTPException(400, "Invalid ObjectId")
    return ObjectId(x)

@router.get("/me")
async def get_my_profile(db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    prof = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not prof:
        return {"exists": False}
    prof["_id"] = str(prof["_id"]); prof["user_id"] = str(prof["user_id"])
    return prof

@router.put("/me")
async def upsert_my_profile(payload: dict, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    doc = {
        "user_id": ObjectId(x_user_id),
        "bio": payload.get("bio",""),
        "budget": float(payload.get("budget", 0)) if payload.get("budget") is not None else 0,
        "desiredAreas": payload.get("desiredAreas", []),
        "habits": payload.get("habits", {}),  # e.g., {"smoke": False, "pet": True, "cook": True, "sleepTime":"early"}
        "gender": payload.get("gender"),
        "age": payload.get("age"),
        "constraints": payload.get("constraints", {}), # hard filters like genderWanted, ageRange, etc.
        "location": payload.get("location"),  # optional {"type":"Point","coordinates":[lng,lat]}
    }
    await db.profiles.update_one({"user_id": ObjectId(x_user_id)}, {"$set": doc}, upsert=True)
    prof = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    prof["_id"] = str(prof["_id"]); prof["user_id"] = str(prof["user_id"])
    return prof

@router.get("/search")
async def search_profiles(
    q: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    page: int = 1, limit: int = 20,
    db = Depends(get_db)
):
    filt: dict[str, Any] = {}
    price = {}
    if min_budget is not None: price["$gte"] = float(min_budget)
    if max_budget is not None: price["$lte"] = float(max_budget)
    if price: filt["budget"] = price
    # simple full-text like on bio if text index exists later
    if q: filt["bio"] = {"$regex": q, "$options": "i"}
    skip = max(0, (page-1)*min(limit,100))
    cur = db.profiles.find(filt).skip(skip).limit(min(limit,100)).sort([("_id",-1)])
    items = []
    async for p in cur:
        p["_id"] = str(p["_id"]); p["user_id"] = str(p["user_id"])
        items.append(p)
    total = await db.profiles.count_documents(filt)
    return {"items": items, "page": page, "limit": min(limit,100), "total": total}
