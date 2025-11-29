from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Any, List, Optional
from bson import ObjectId
from datetime import datetime
import httpx
from ..db import get_db
from ..schemas import ListingIn, ListingPatch, ListingOut
from ..utils.pagination import build_pagination

router = APIRouter(prefix="/listings", tags=["listings"])

def shorten_address(full_address: str) -> str:
    if not full_address:
        return ""
    parts = full_address.split(", ")
    if len(parts) <= 2:
        return full_address
    vietnam_keywords = ["Việt Nam", "Vietnam", "VN"]
    filtered = [p for p in parts if not any(kw.lower() in p.lower() for kw in vietnam_keywords)]
    relevant = [p for p in filtered if not p.strip().isdigit()]
    if len(relevant) <= 2:
        return ", ".join(relevant)
    return ", ".join(relevant[-2:])

async def reverse_geocode(lng: float, lat: float) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "format": "json",
                    "lat": lat,
                    "lon": lng,
                    "accept-language": "vi"
                },
                headers={"User-Agent": "TroHub/1.0"}
            )
            data = resp.json()
            if data.get("display_name"):
                return shorten_address(data["display_name"])
    except:
        pass
    return f"{lat:.4f}, {lng:.4f}"

@router.post("", status_code=201, response_model=ListingOut)
async def create_listing(payload: ListingIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(401, "Không tìm thấy người dùng")
    if not user.get("is_verified"):
        raise HTTPException(403, "Bạn cần xác thực email trước khi đăng tin")
    doc = payload.model_dump()
    doc["owner_id"] = ObjectId(x_user_id)
    doc["verification_status"] = "PENDING"
    doc["verified_by"] = None
    doc["verified_at"] = None
    
    if not doc.get("address") and doc.get("location", {}).get("coordinates"):
        coords = doc["location"]["coordinates"]
        doc["address"] = await reverse_geocode(coords[0], coords[1])
    
    res = await db.listings.insert_one(doc)
    saved = await db.listings.find_one({"_id": res.inserted_id})
    
    return ListingOut(
        _id=str(saved["_id"]),
        owner_id=str(saved["owner_id"]),
        title=saved.get("title", ""),
        desc=saved.get("desc", ""),
        price=saved.get("price", 0),
        area=saved.get("area", 0),
        amenities=saved.get("amenities", []),
        rules=saved.get("rules", {}),
        images=saved.get("images", []),
        video=saved.get("video"),
        status=saved.get("status", "ACTIVE"),
        location=saved.get("location"),
        address=saved.get("address"),
        verification_status=saved.get("verification_status", "PENDING"),
        verified_by=str(saved["verified_by"]) if saved.get("verified_by") else None,
        verified_at=saved.get("verified_at")
    )

@router.get("", summary="Query listings with filters and geo search")
async def list_listings(
    q: Optional[str] = Query(None, description="keyword search on title/desc"),
    province: Optional[str] = Query(None, description="filter by province/city name"),
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_area: Optional[float] = None,
    max_area: Optional[float] = None,
    amenities: Optional[str] = Query(None, description="comma-separated amenities"),
    pet: Optional[bool] = Query(None, description="pet allowed"),
    smoke: Optional[bool] = Query(None, description="smoking allowed"),
    cook: Optional[bool] = Query(None, description="cooking allowed"),
    visitor: Optional[bool] = Query(None, description="visitors allowed"),
    lng: Optional[float] = Query(None, description="longitude"),
    lat: Optional[float] = Query(None, description="latitude"),
    radius_km: Optional[float] = Query(5, description="search radius in KM"),
    exclude_own: Optional[bool] = Query(False, description="exclude current user's listings"),
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None),
):
    filters: dict[str, Any] = {"status": {"$ne": "HIDDEN"}}
    
    is_admin = False
    if x_user_id and ObjectId.is_valid(x_user_id):
        user = await db.users.find_one({"_id": ObjectId(x_user_id)})
        if user and user.get("role") == "ADMIN":
            is_admin = True
        
        if exclude_own:
            filters["owner_id"] = {"$ne": ObjectId(x_user_id)}
    
    if not is_admin:
        filters["verification_status"] = "VERIFIED"
    
    if q:
        filters["$text"] = {"$search": q}
    
    if province:
        province_clean = province.replace("Thành phố ", "").replace("Tỉnh ", "").strip()
        filters["address"] = {"$regex": province_clean, "$options": "i"}
    
    price_cond = {}
    if min_price is not None:
        price_cond["$gte"] = float(min_price)
    if max_price is not None:
        price_cond["$lte"] = float(max_price)
    if price_cond:
        filters["price"] = price_cond
    
    area_cond = {}
    if min_area is not None:
        area_cond["$gte"] = float(min_area)
    if max_area is not None:
        area_cond["$lte"] = float(max_area)
    if area_cond:
        filters["area"] = area_cond
    
    if amenities:
        amenities_list = [a.strip() for a in amenities.split(",") if a.strip()]
        if amenities_list:
            filters["amenities"] = {"$all": amenities_list}
    
    if pet is not None:
        filters["rules.pet"] = pet
    if smoke is not None:
        filters["rules.smoke"] = smoke
    if cook is not None:
        filters["rules.cook"] = cook
    if visitor is not None:
        filters["rules.visitor"] = visitor
    if lng is not None and lat is not None:
        
        radius_m = float(radius_km or 5) * 1000.0
        filters["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                "$maxDistance": radius_m
            }
        }

    pag = build_pagination(page, limit)
    cursor = db.listings.find(filters).skip(pag["skip"]).limit(pag["limit"])
    cursor = cursor.sort([("_id", -1)])  
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["owner_id"] = str(doc["owner_id"])
        if doc.get("verified_by"):
            doc["verified_by"] = str(doc["verified_by"])
        items.append(doc)
    
    if "location" in filters and isinstance(filters["location"], dict) and "$near" in filters["location"]:
        near = filters["location"]["$near"]
        geometry = near.get("$geometry")
        maxDistance = near.get("$maxDistance")
        
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

@router.get("/my", summary="Get current user's listings")
async def get_my_listings(
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    filters = {"owner_id": ObjectId(x_user_id)}
    pag = build_pagination(page, limit)
    
    cursor = db.listings.find(filters).sort([("_id", -1)]).skip(pag["skip"]).limit(pag["limit"])
    
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        doc["owner_id"] = str(doc["owner_id"])
        if doc.get("verified_by"):
            doc["verified_by"] = str(doc["verified_by"])
        items.append(doc)
    
    total = await db.listings.count_documents(filters)
    return {"items": items, "page": pag["page"], "limit": pag["limit"], "total": total}

@router.get("/{listing_id}")
async def get_listing(listing_id: str, db = Depends(get_db)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    doc = await db.listings.find_one({"_id": ObjectId(listing_id)})
    if not doc:
        raise HTTPException(404, "Không tìm thấy tin đăng")
    doc["_id"] = str(doc["_id"])
    doc["owner_id"] = str(doc["owner_id"])
    if doc.get("verified_by"):
        doc["verified_by"] = str(doc["verified_by"])
    
    owner = await db.users.find_one({"_id": ObjectId(doc["owner_id"])})
    if owner:
        doc["owner"] = {
            "_id": str(owner["_id"]),
            "name": owner.get("name", ""),
            "phone": owner.get("phone", ""),
            "email": owner.get("email", "")
        }
    
    return doc

@router.patch("/{listing_id}")
async def patch_listing(listing_id: str, payload: ListingPatch, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    update = {"$set": {k: v for k, v in payload.model_dump(exclude_none=True).items()}}
    if not update["$set"]:
        return {"updated": False}
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    res = await db.listings.update_one({"_id": ObjectId(listing_id), "owner_id": ObjectId(x_user_id)}, update)
    if res.matched_count == 0:
        raise HTTPException(404, "Không tìm thấy tin đăng")
    doc = await db.listings.find_one({"_id": ObjectId(listing_id)})
    doc["_id"] = str(doc["_id"])
    doc["owner_id"] = str(doc["owner_id"])
    if doc.get("verified_by"):
        doc["verified_by"] = str(doc["verified_by"])
    return doc

@router.delete("/{listing_id}", status_code=204)
async def delete_listing(listing_id: str, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    await db.listings.delete_one({"_id": ObjectId(listing_id), "owner_id": ObjectId(x_user_id)})
    return

@router.post("/{listing_id}/verify", summary="Admin verify listing")
async def verify_listing(
    listing_id: str,
    status: str = Query(..., description="VERIFIED or REJECTED"),
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    admin = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not admin or admin.get("role") != "ADMIN":
        raise HTTPException(403, "Chỉ admin mới có quyền xác thực tin đăng")
    
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    
    if status not in ["VERIFIED", "REJECTED"]:
        raise HTTPException(400, "Trạng thái phải là VERIFIED hoặc REJECTED")
    
    listing = await db.listings.find_one({"_id": ObjectId(listing_id)})
    if not listing:
        raise HTTPException(404, "Không tìm thấy tin đăng")
    
    update = {
        "$set": {
            "verification_status": status,
            "verified_by": ObjectId(x_user_id),
            "verified_at": datetime.utcnow().isoformat()
        }
    }
    
    await db.listings.update_one({"_id": ObjectId(listing_id)}, update)
    
    updated = await db.listings.find_one({"_id": ObjectId(listing_id)})
    updated["_id"] = str(updated["_id"])
    updated["owner_id"] = str(updated["owner_id"])
    if updated.get("verified_by"):
        updated["verified_by"] = str(updated["verified_by"])
    
    return updated

@router.post("/migrate-addresses", summary="Backfill addresses for existing listings")
async def migrate_addresses(
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    admin = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not admin or admin.get("role") != "ADMIN":
        raise HTTPException(403, "Chỉ admin mới có quyền thực hiện migration")
    
    cursor = db.listings.find({"$or": [{"address": None}, {"address": {"$exists": False}}]})
    updated_count = 0
    errors = []
    
    async for listing in cursor:
        try:
            coords = listing.get("location", {}).get("coordinates", [])
            if len(coords) == 2:
                lng, lat = coords
                address = await reverse_geocode(lng, lat)
                await db.listings.update_one(
                    {"_id": listing["_id"]},
                    {"$set": {"address": address}}
                )
                updated_count += 1
        except Exception as e:
            errors.append({"id": str(listing["_id"]), "error": str(e)})
    
    return {
        "updated": updated_count,
        "errors": errors
    }
