from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Any, List, Optional
from bson import ObjectId
from ..db import get_db
from ..schemas import ListingIn, ListingPatch
from ..utils.pagination import build_pagination

router = APIRouter(prefix="/listings", tags=["listings"])

@router.post("", status_code=201)
async def create_listing(payload: ListingIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    doc = payload.model_dump()
    doc["owner_id"] = ObjectId(x_user_id)
    res = await db.listings.insert_one(doc)
    saved = await db.listings.find_one({"_id": res.inserted_id})
    saved["_id"] = str(saved["_id"])
    saved["owner_id"] = str(saved["owner_id"])
    return saved

@router.get("", summary="Query listings with filters and geo search")
async def list_listings(
    q: Optional[str] = Query(None, description="keyword search on title/desc"),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    lng: Optional[float] = Query(None, description="longitude"),
    lat: Optional[float] = Query(None, description="latitude"),
    radius_km: Optional[float] = Query(5, description="search radius in KM"),
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
):
    filters: dict[str, Any] = {"status": {"$ne": "HIDDEN"}}
    if q:
        filters["$text"] = {"$search": q}
    price_cond = {}
    if min_price is not None:
        price_cond["$gte"] = float(min_price)
    if max_price is not None:
        price_cond["$lte"] = float(max_price)
    if price_cond:
        filters["price"] = price_cond
    if lng is not None and lat is not None:
        # meters
        radius_m = float(radius_km or 5) * 1000.0
        filters["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                "$maxDistance": radius_m
            }
        }

    pag = build_pagination(page, limit)
    cursor = db.listings.find(filters).skip(pag["skip"]).limit(pag["limit"])
    cursor = cursor.sort([("_id", -1)])  # newest first
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["owner_id"] = str(doc["owner_id"])
        items.append(doc)
    # count_documents does not accept $near/$geoNear in the filter (MongoDB will error).
    # If a geo $near filter was used, run an aggregation with $geoNear as the first stage
    # and then $count. Otherwise fall back to count_documents.
    if "location" in filters and isinstance(filters["location"], dict) and "$near" in filters["location"]:
        near = filters["location"]["$near"]
        geometry = near.get("$geometry")
        maxDistance = near.get("$maxDistance")
        # other filters (exclude the location/$near part)
        other_filters = {k: v for k, v in filters.items() if k != "location"}
        geo_near_stage: dict = {
            "$geoNear": {
                "near": geometry,
                "distanceField": "dist",
                "spherical": True,
            }
        }
        if maxDistance is not None:
            geo_near_stage["$geoNear"]["maxDistance"] = maxDistance
        if other_filters:
            geo_near_stage["$geoNear"]["query"] = other_filters

        pipeline = [geo_near_stage, {"$count": "count"}]
        agg_res = await db.listings.aggregate(pipeline).to_list(length=1)
        total = agg_res[0]["count"] if agg_res else 0
    else:
        total = await db.listings.count_documents(filters)
    return {"items": items, "page": pag["page"], "limit": pag["limit"], "total": total}

@router.get("/{listing_id}")
async def get_listing(listing_id: str, db = Depends(get_db)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "Invalid listing id")
    doc = await db.listings.find_one({"_id": ObjectId(listing_id)})
    if not doc:
        raise HTTPException(404, "Listing not found")
    doc["_id"] = str(doc["_id"])
    doc["owner_id"] = str(doc["owner_id"])
    return doc

@router.patch("/{listing_id}")
async def patch_listing(listing_id: str, payload: ListingPatch, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "Invalid listing id")
    update = {"$set": {k: v for k, v in payload.model_dump(exclude_none=True).items()}}
    if not update["$set"]:
        return {"updated": False}
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    # owner-only update
    res = await db.listings.update_one({"_id": ObjectId(listing_id), "owner_id": ObjectId(x_user_id)}, update)
    if res.matched_count == 0:
        raise HTTPException(404, "Listing not found")
    doc = await db.listings.find_one({"_id": ObjectId(listing_id)})
    doc["_id"] = str(doc["_id"])
    doc["owner_id"] = str(doc["owner_id"])
    return doc

@router.delete("/{listing_id}", status_code=204)
async def delete_listing(listing_id: str, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "Invalid listing id")
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Missing or invalid X-User-Id")
    await db.listings.delete_one({"_id": ObjectId(listing_id), "owner_id": ObjectId(x_user_id)})
    return
