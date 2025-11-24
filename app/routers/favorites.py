from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Any, List, Optional
from bson import ObjectId
from ..db import get_db
from ..schemas import FavoriteIn, FavoriteOut, ListingPreviewOut

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.post("", status_code=201)
async def add_favorite(payload: FavoriteIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    listing_id = payload.listing_id
    if not listing_id or not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    await db.favorites.update_one(
        {"user_id": ObjectId(x_user_id), "listing_id": ObjectId(listing_id)},
        {"$set": {"user_id": ObjectId(x_user_id), "listing_id": ObjectId(listing_id)}},
        upsert=True
    )
    return {"ok": True}

@router.get("", response_model=dict)
async def list_favorites(db = Depends(get_db), x_user_id: Optional[str] = Header(None), page: int = 1, limit: int = 20):
    """List user's favorites with listing previews"""
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    skip = max(0, (page-1)*min(limit,100))
    cur = db.favorites.find({"user_id": ObjectId(x_user_id)}).skip(skip).limit(min(limit,100)).sort([("_id",-1)])
    items = []
    async for f in cur:
        favorite_out = FavoriteOut(
            _id=str(f["_id"]),
            user_id=str(f["user_id"]),
            listing_id=str(f["listing_id"])
        )
        
        listing = await db.listings.find_one({"_id": f["listing_id"]})
        if listing:
            favorite_out.listing = ListingPreviewOut(
                _id=str(listing["_id"]),
                title=listing.get("title", ""),
                desc=listing.get("desc", ""),
                price=listing.get("price", 0),
                area=listing.get("area", 0),
                images=listing.get("images", []),
                location=listing.get("location", {"type": "Point", "coordinates": [0, 0]}),
                status=listing.get("status", "ACTIVE"),
                owner_id=str(listing.get("owner_id", ""))
            )
        else:
            favorite_out.listing = None
            
        items.append(favorite_out.model_dump(by_alias=True))
    total = await db.favorites.count_documents({"user_id": ObjectId(x_user_id)})
    return {"items": items, "page": page, "limit": min(limit,100), "total": total}

@router.delete("")
async def remove_favorite(listing_id: str, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    await db.favorites.delete_one({"user_id": ObjectId(x_user_id), "listing_id": ObjectId(listing_id)})
    return {"ok": True}
