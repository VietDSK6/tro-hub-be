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

@router.get("/rooms")
async def match_rooms(
    top_k: int = 10,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Match user profile with available room listings based on budget and location"""
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    me = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not me: 
        raise HTTPException(400, "Bạn cần tạo hồ sơ của mình trước")
    
    me_loc = (me.get("location") or {}).get("coordinates")
    me_budget = float(me.get("budget") or 0)

    # Only get verified and active listings
    candidates = db.listings.find({
        "verification_status": "VERIFIED",
        "status": "ACTIVE"
    }).limit(500)
    
    scored: list[dict[str,Any]] = []
    async for listing in candidates:
        listing_loc = (listing.get("location") or {}).get("coordinates")
        listing_price = float(listing.get("price") or 0)

        # Calculate scores
        # Budget score: how close the price is to user's budget
        if me_budget > 0 and listing_price > 0:
            budget_diff = abs(me_budget - listing_price)
            budget = max(0.0, 1.0 - (budget_diff / me_budget))
        else:
            budget = 0.5  # neutral if no budget set
        
        # Distance score
        dist_km = _distance_km(me_loc, listing_loc)
        if dist_km is None:
            distance = 0.5  # neutral if no location
        else:
            # Within 5km is best, beyond 20km is worst
            distance = max(0.0, 1.0 - (dist_km / 20.0))
        
        # Overall score: budget is most important, then distance
        score = 0.7 * budget + 0.3 * distance
        
        # Only include listings with reasonable match
        if score < 0.2:
            continue
        
        # Fetch owner info
        owner = await db.users.find_one({"_id": listing["owner_id"]})
        owner_name = owner.get("name", "") if owner else ""
        
        listing_dto = {
            "_id": str(listing["_id"]),
            "title": listing.get("title", ""),
            "desc": listing.get("desc", ""),
            "price": listing.get("price", 0),
            "area": listing.get("area", 0),
            "amenities": listing.get("amenities", []),
            "images": listing.get("images", []),
            "location": listing.get("location"),
            "owner_id": str(listing["owner_id"]),
            "owner_name": owner_name,
            "verification_status": listing.get("verification_status", "PENDING"),
        }
        
        scored.append({
            "listing": listing_dto,
            "score": round(score, 3),
            "distance_km": None if dist_km is None else round(dist_km, 2),
            "price_match": round(budget, 3)
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"items": scored[:max(1, min(top_k, 50))]}


@router.get("/roommates")
async def match_roommates(
    top_k: int = 10,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Match roommates based on budget, habits, and location (DEPRECATED - use /rooms instead)"""
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    me = await db.profiles.find_one({"user_id": ObjectId(x_user_id)})
    if not me: raise HTTPException(400, "Bạn cần tạo hồ sơ của mình trước")
    
    return {"items": [], "message": "This endpoint is deprecated. Use /matching/rooms instead"}

