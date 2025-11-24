from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Optional, Any, List
from bson import ObjectId
from ..db import get_db
from ..schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])

def _oid(x: str) -> ObjectId:
    if not ObjectId.is_valid(x):
        raise HTTPException(400, "ObjectId không hợp lệ")
    return ObjectId(x)

@router.get("/me", response_model=ProfileOut)
async def get_my_profile(db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    """Get current user's profile with user info"""
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    prof = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not prof:
        default_prof = {
            "user_id": ObjectId(x_user_id),
            "bio": "",
            "budget": 0,
            "desiredAreas": [],
            "habits": {},
            "gender": None,
            "age": None,
            "constraints": {},
            "location": None,
        }
        result = await db.profiles.insert_one(default_prof)
        prof = await db.profiles.find_one({"_id": result.inserted_id})
    
    return ProfileOut(
        _id=str(prof["_id"]),
        user_id=str(prof["user_id"]),
        bio=prof.get("bio", ""),
        budget=prof.get("budget", 0),
        desiredAreas=prof.get("desiredAreas", []),
        habits=prof.get("habits", {}),
        gender=prof.get("gender"),
        age=prof.get("age"),
        constraints=prof.get("constraints", {}),
        location=prof.get("location"),
        full_name=user.get("name", ""),
        email=user.get("email", ""),
        phone=user.get("phone", ""),
        role=user.get("role", "USER")
    )

@router.put("/me", response_model=ProfileOut)
async def upsert_my_profile(payload: ProfileIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    """Update or create current user's profile"""
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    # Update user fields if provided
    user_update = {}
    if payload.full_name is not None:
        user_update["name"] = payload.full_name
    if payload.email is not None:
        # Check if email already exists for another user
        existing_user = await db.users.find_one({"email": payload.email, "_id": {"$ne": ObjectId(x_user_id)}})
        if existing_user:
            raise HTTPException(400, "Email đã được sử dụng bởi tài khoản khác")
        user_update["email"] = payload.email
    
    if user_update:
        await db.users.update_one({"_id": ObjectId(x_user_id)}, {"$set": user_update})
    
    # Update profile fields
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
    
    # Fetch updated user and profile data
    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    prof = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    
    return ProfileOut(
        _id=str(prof["_id"]),
        user_id=str(prof["user_id"]),
        bio=prof.get("bio", ""),
        budget=prof.get("budget", 0),
        desiredAreas=prof.get("desiredAreas", []),
        habits=prof.get("habits", {}),
        gender=prof.get("gender"),
        age=prof.get("age"),
        constraints=prof.get("constraints", {}),
        location=prof.get("location"),
        full_name=user.get("name", ""),
        email=user.get("email", ""),
        phone=user.get("phone", ""),
        role=user.get("role", "USER")
    )

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
