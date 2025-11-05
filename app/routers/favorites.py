from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Any, List, Optional
from bson import ObjectId
from ..db import get_db

router = APIRouter(prefix="/favorites", tags=["favorites"])

@router.post("", status_code=201)
async def add_favorite(payload: dict, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    listing_id = payload.get("listing_id")
    if not listing_id or not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "Invalid listing_id")
    await db.favorites.update_one(
        {"user_id": ObjectId(x_user_id), "listing_id": ObjectId(listing_id)},
        {"$set": {"user_id": ObjectId(x_user_id), "listing_id": ObjectId(listing_id)}},
        upsert=True
    )
    return {"ok": True}

@router.get("")
async def list_favorites(db = Depends(get_db), x_user_id: Optional[str] = Header(None), page: int = 1, limit: int = 20):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    skip = max(0, (page-1)*min(limit,100))
    cur = db.favorites.find({"user_id": ObjectId(x_user_id)}).skip(skip).limit(min(limit,100)).sort([("_id",-1)])
    items = []
    async for f in cur:
        f["_id"] = str(f["_id"]); 
        f["user_id"] = str(f["user_id"]); 
        listing_id_obj = f["listing_id"]
        f["listing_id"] = str(listing_id_obj)
        
        listing = await db.listings.find_one({"_id": listing_id_obj})
        if listing:
            f["listing"] = {
                "_id": str(listing["_id"]),
                "title": listing.get("title", ""),
                "desc": listing.get("desc", ""),
                "price": listing.get("price", 0),
                "location": listing.get("location")
            }
        else:
            f["listing"] = None
            
        items.append(f)
    total = await db.favorites.count_documents({"user_id": ObjectId(x_user_id)})
    return {"items": items, "page": page, "limit": min(limit,100), "total": total}

@router.delete("")
async def remove_favorite(listing_id: str, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "Invalid listing_id")
    await db.favorites.delete_one({"user_id": ObjectId(x_user_id), "listing_id": ObjectId(listing_id)})
    return {"ok": True}
