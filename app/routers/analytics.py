from fastapi import APIRouter, Depends
from typing import Any, Dict, List
from bson import ObjectId
from ..db import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/overview", summary="Get overview statistics of all listings")
async def get_overview_analytics(db = Depends(get_db)):
    """
    Get comprehensive analytics including:
    - Total listings, active, rented, hidden
    - Average price, min, max
    - Average area
    - Price distribution by ranges
    - Area distribution
    - Top amenities
    - Status breakdown
    """
    
    total_listings = await db.listings.count_documents({})
    active_listings = await db.listings.count_documents({"status": "ACTIVE", "verification_status": "VERIFIED"})
    rented_listings = await db.listings.count_documents({"status": "RENTED"})
    hidden_listings = await db.listings.count_documents({"status": "HIDDEN"})
    pending_listings = await db.listings.count_documents({"verification_status": "PENDING"})
    
    price_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$group": {
            "_id": None,
            "avg_price": {"$avg": "$price"},
            "min_price": {"$min": "$price"},
            "max_price": {"$max": "$price"},
            "avg_area": {"$avg": "$area"}
        }}
    ]
    price_stats = await db.listings.aggregate(price_pipeline).to_list(length=1)
    price_data = price_stats[0] if price_stats else {
        "avg_price": 0,
        "min_price": 0,
        "max_price": 0,
        "avg_area": 0
    }
    
    price_distribution_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$bucket": {
            "groupBy": "$price",
            "boundaries": [0, 1000000, 2000000, 3000000, 4000000, 5000000, 10000000, 50000000],
            "default": "50000000+",
            "output": {"count": {"$sum": 1}}
        }}
    ]
    price_distribution = [doc async for doc in db.listings.aggregate(price_distribution_pipeline)]
    
    area_distribution_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$bucket": {
            "groupBy": "$area",
            "boundaries": [0, 15, 20, 25, 30, 40, 50, 100],
            "default": "100+",
            "output": {"count": {"$sum": 1}}
        }}
    ]
    area_distribution = [doc async for doc in db.listings.aggregate(area_distribution_pipeline)]
    
    amenities_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$unwind": "$amenities"},
        {"$group": {"_id": "$amenities", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_amenities = [doc async for doc in db.listings.aggregate(amenities_pipeline)]
    
    verification_status_pipeline = [
        {"$group": {"_id": "$verification_status", "count": {"$sum": 1}}}
    ]
    verification_status = [doc async for doc in db.listings.aggregate(verification_status_pipeline)]
    
    return {
        "total_listings": total_listings,
        "active_listings": active_listings,
        "rented_listings": rented_listings,
        "hidden_listings": hidden_listings,
        "pending_listings": pending_listings,
        "price_stats": {
            "average": round(price_data.get("avg_price", 0), 0),
            "min": price_data.get("min_price", 0),
            "max": price_data.get("max_price", 0)
        },
        "area_stats": {
            "average": round(price_data.get("avg_area", 0), 2)
        },
        "price_distribution": price_distribution,
        "area_distribution": area_distribution,
        "top_amenities": top_amenities,
        "verification_status": verification_status
    }

@router.get("/by-location", summary="Get listings distribution by location/area")
async def get_location_analytics(db = Depends(get_db)):
    """
    Get analytics grouped by geographic areas using coordinate clustering
    Returns areas with most listings
    """
    
    location_pipeline = [
        {"$match": {
            "status": "ACTIVE", 
            "verification_status": "VERIFIED",
            "location": {"$exists": True}
        }},
        {"$addFields": {
            "lng_rounded": {"$round": [{"$arrayElemAt": ["$location.coordinates", 0]}, 2]},
            "lat_rounded": {"$round": [{"$arrayElemAt": ["$location.coordinates", 1]}, 2]}
        }},
        {"$group": {
            "_id": {
                "lng": "$lng_rounded",
                "lat": "$lat_rounded"
            },
            "count": {"$sum": 1},
            "avg_price": {"$avg": "$price"},
            "min_price": {"$min": "$price"},
            "max_price": {"$max": "$price"},
            "avg_area": {"$avg": "$area"}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    
    location_data = [doc async for doc in db.listings.aggregate(location_pipeline)]
    
    return {
        "top_locations": [
            {
                "coordinates": [doc["_id"]["lng"], doc["_id"]["lat"]],
                "count": doc["count"],
                "avg_price": round(doc["avg_price"], 0),
                "min_price": doc["min_price"],
                "max_price": doc["max_price"],
                "avg_area": round(doc["avg_area"], 2)
            }
            for doc in location_data
        ]
    }

@router.get("/by-price-range", summary="Get detailed price range analytics")
async def get_price_range_analytics(db = Depends(get_db)):
    """
    Get detailed breakdown of listings by price ranges
    """
    
    price_ranges = [
        {"label": "Dưới 1 triệu", "min": 0, "max": 1000000},
        {"label": "1-2 triệu", "min": 1000000, "max": 2000000},
        {"label": "2-3 triệu", "min": 2000000, "max": 3000000},
        {"label": "3-4 triệu", "min": 3000000, "max": 4000000},
        {"label": "4-5 triệu", "min": 4000000, "max": 5000000},
        {"label": "5-10 triệu", "min": 5000000, "max": 10000000},
        {"label": "Trên 10 triệu", "min": 10000000, "max": 100000000}
    ]
    
    results = []
    for range_def in price_ranges:
        count = await db.listings.count_documents({
            "status": "ACTIVE",
            "verification_status": "VERIFIED",
            "price": {"$gte": range_def["min"], "$lt": range_def["max"]}
        })
        
        avg_pipeline = [
            {"$match": {
                "status": "ACTIVE",
                "verification_status": "VERIFIED",
                "price": {"$gte": range_def["min"], "$lt": range_def["max"]}
            }},
            {"$group": {
                "_id": None,
                "avg_area": {"$avg": "$area"}
            }}
        ]
        avg_result = await db.listings.aggregate(avg_pipeline).to_list(length=1)
        avg_area = round(avg_result[0]["avg_area"], 2) if avg_result else 0
        
        results.append({
            "label": range_def["label"],
            "min_price": range_def["min"],
            "max_price": range_def["max"],
            "count": count,
            "avg_area": avg_area
        })
    
    return {"price_ranges": results}

@router.get("/by-area-range", summary="Get detailed area range analytics")
async def get_area_range_analytics(db = Depends(get_db)):
    """
    Get detailed breakdown of listings by area ranges
    """
    
    area_ranges = [
        {"label": "Dưới 15m²", "min": 0, "max": 15},
        {"label": "15-20m²", "min": 15, "max": 20},
        {"label": "20-25m²", "min": 20, "max": 25},
        {"label": "25-30m²", "min": 25, "max": 30},
        {"label": "30-40m²", "min": 30, "max": 40},
        {"label": "40-50m²", "min": 40, "max": 50},
        {"label": "Trên 50m²", "min": 50, "max": 1000}
    ]
    
    results = []
    for range_def in area_ranges:
        count = await db.listings.count_documents({
            "status": "ACTIVE",
            "verification_status": "VERIFIED",
            "area": {"$gte": range_def["min"], "$lt": range_def["max"]}
        })
        
        avg_pipeline = [
            {"$match": {
                "status": "ACTIVE",
                "verification_status": "VERIFIED",
                "area": {"$gte": range_def["min"], "$lt": range_def["max"]}
            }},
            {"$group": {
                "_id": None,
                "avg_price": {"$avg": "$price"}
            }}
        ]
        avg_result = await db.listings.aggregate(avg_pipeline).to_list(length=1)
        avg_price = round(avg_result[0]["avg_price"], 0) if avg_result else 0
        
        results.append({
            "label": range_def["label"],
            "min_area": range_def["min"],
            "max_area": range_def["max"],
            "count": count,
            "avg_price": avg_price
        })
    
    return {"area_ranges": results}

@router.get("/amenities-stats", summary="Get detailed amenities statistics")
async def get_amenities_stats(db = Depends(get_db)):
    """
    Get comprehensive statistics about amenities usage
    """
    
    amenities_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$unwind": "$amenities"},
        {"$group": {
            "_id": "$amenities",
            "count": {"$sum": 1},
            "avg_price": {"$avg": "$price"},
            "avg_area": {"$avg": "$area"}
        }},
        {"$sort": {"count": -1}}
    ]
    
    amenities_data = [doc async for doc in db.listings.aggregate(amenities_pipeline)]
    
    amenities_labels = {
        "ac": "Điều hòa",
        "wifi": "Wifi",
        "parking": "Chỗ để xe",
        "water_heater": "Nóng lạnh",
        "kitchen": "Bếp",
        "washing_machine": "Máy giặt",
        "fridge": "Tủ lạnh",
        "security": "An ninh 24/7",
        "private_room": "Phòng riêng",
        "balcony": "Ban công"
    }
    
    return {
        "amenities": [
            {
                "key": doc["_id"],
                "label": amenities_labels.get(doc["_id"], doc["_id"]),
                "count": doc["count"],
                "avg_price": round(doc["avg_price"], 0),
                "avg_area": round(doc["avg_area"], 2)
            }
            for doc in amenities_data
        ]
    }

@router.get("/rules-stats", summary="Get statistics about listing rules")
async def get_rules_stats(db = Depends(get_db)):
    """
    Get statistics about common rules (pet, smoke, cook, visitor)
    """
    
    rules_keys = ["pet", "smoke", "cook", "visitor"]
    results = {}
    
    for rule_key in rules_keys:
        allowed_count = await db.listings.count_documents({
            "status": "ACTIVE",
            "verification_status": "VERIFIED",
            f"rules.{rule_key}": True
        })
        
        not_allowed_count = await db.listings.count_documents({
            "status": "ACTIVE",
            "verification_status": "VERIFIED",
            f"rules.{rule_key}": False
        })
        
        results[rule_key] = {
            "allowed": allowed_count,
            "not_allowed": not_allowed_count,
            "total": allowed_count + not_allowed_count
        }
    
    return {"rules_stats": results}

@router.get("/trends", summary="Get trending insights and recommendations")
async def get_trends(db = Depends(get_db)):
    """
    Get trending insights like most popular price range, area, amenities combinations
    """
    
    most_common_price_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$bucket": {
            "groupBy": "$price",
            "boundaries": [0, 1000000, 2000000, 3000000, 4000000, 5000000, 10000000],
            "default": "10000000+",
            "output": {"count": {"$sum": 1}}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 1}
    ]
    most_common_price = await db.listings.aggregate(most_common_price_pipeline).to_list(length=1)
    
    most_common_area_pipeline = [
        {"$match": {"status": "ACTIVE", "verification_status": "VERIFIED"}},
        {"$bucket": {
            "groupBy": "$area",
            "boundaries": [0, 15, 20, 25, 30, 40, 50],
            "default": "50+",
            "output": {"count": {"$sum": 1}}
        }},
        {"$sort": {"count": -1}},
        {"$limit": 1}
    ]
    most_common_area = await db.listings.aggregate(most_common_area_pipeline).to_list(length=1)
    
    total_active = await db.listings.count_documents({"status": "ACTIVE", "verification_status": "VERIFIED"})
    
    return {
        "most_common_price_range": most_common_price[0] if most_common_price else None,
        "most_common_area_range": most_common_area[0] if most_common_area else None,
        "total_active_listings": total_active
    }
