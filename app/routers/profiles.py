from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Optional, Any, List
from bson import ObjectId
from ..db import get_db
from ..schemas import ProfileIn

router = APIRouter(prefix="/profiles", tags=["profiles"])

def _oid(x: str) -> ObjectId:
    if not ObjectId.is_valid(x):
        raise HTTPException(400, "ObjectId không hợp lệ")
    return ObjectId(x)

@router.get("/me")
async def get_my_profile(db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    prof = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not prof:
        return {"exists": False}
    prof["_id"] = str(prof["_id"]); prof["user_id"] = str(prof["user_id"])
    return prof

@router.put("/me")
async def upsert_my_profile(payload: ProfileIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    doc = {
        "user_id": ObjectId(x_user_id),
        "bio": payload.bio,
        "budget": float(payload.budget) if payload.budget is not None else 0,
        "desiredAreas": payload.desiredAreas,
        "habits": payload.habits,
        "gender": payload.gender,
        "age": payload.age,
        "constraints": payload.constraints,
        "location": payload.location.model_dump() if payload.location else None,
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
    if q: filt["bio"] = {"$regex": q, "$options": "i"}
    skip = max(0, (page-1)*min(limit,100))
    cur = db.profiles.find(filt).skip(skip).limit(min(limit,100)).sort([("_id",-1)])
    items = []
    async for p in cur:
        p["_id"] = str(p["_id"]); p["user_id"] = str(p["user_id"])
        items.append(p)
    total = await db.profiles.count_documents(filt)
    return {"items": items, "page": page, "limit": min(limit,100), "total": total}
