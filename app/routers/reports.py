from fastapi import APIRouter, Depends, HTTPException, Header, Query
from typing import Optional
from bson import ObjectId
from datetime import datetime
from ..db import get_db
from ..schemas import ReportIn

router = APIRouter(prefix="/reports", tags=["reports"])

def _oid_ok(x: str) -> bool:
    return ObjectId.is_valid(x)

@router.post("", status_code=201)
async def report_listing(payload: ReportIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(401, "Không tìm thấy người dùng")
    if not user.get("is_verified"):
        raise HTTPException(403, "Bạn cần xác thực email trước khi báo cáo")
    
    listing_id = payload.listing_id
    reason = payload.reason.strip()
    if not listing_id or not _oid_ok(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    if not reason:
        raise HTTPException(400, "Lý do báo cáo là bắt buộc")
    
    listing = await db.listings.find_one({"_id": ObjectId(listing_id)})
    if not listing:
        raise HTTPException(404, "Không tìm thấy tin đăng")
    
    existing = await db.reports.find_one({
        "listing_id": ObjectId(listing_id),
        "reporter_id": ObjectId(x_user_id),
        "status": "OPEN"
    })
    if existing:
        raise HTTPException(400, "Bạn đã báo cáo tin này rồi")
    
    doc = {
        "listing_id": ObjectId(listing_id),
        "reporter_id": ObjectId(x_user_id),
        "reason": reason,
        "status": "OPEN",
        "created_at": datetime.utcnow()
    }
    await db.reports.insert_one(doc)
    return {"ok": True}

@router.get("")
async def list_reports(
    status: Optional[str] = Query(None, description="OPEN, RESOLVED, DISMISSED"),
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    admin = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not admin or admin.get("role") != "ADMIN":
        raise HTTPException(403, "Chỉ admin mới có quyền xem báo cáo")
    
    filters = {}
    if status:
        filters["status"] = status
    
    skip = max(0, (page - 1) * min(limit, 100))
    cursor = db.reports.find(filters).sort("created_at", -1).skip(skip).limit(min(limit, 100))
    
    items = []
    async for doc in cursor:
        listing = await db.listings.find_one({"_id": doc["listing_id"]})
        reporter = await db.users.find_one({"_id": doc["reporter_id"]})
        
        listing_data = None
        if listing:
            listing_data = {
                "_id": str(listing["_id"]),
                "title": listing.get("title", ""),
                "images": listing.get("images", []),
                "price": listing.get("price", 0),
                "owner_id": str(listing.get("owner_id", ""))
            }
        
        items.append({
            "_id": str(doc["_id"]),
            "listing_id": str(doc["listing_id"]),
            "reporter_id": str(doc["reporter_id"]),
            "reason": doc.get("reason", ""),
            "status": doc.get("status", "OPEN"),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
            "listing": listing_data,
            "reporter": {
                "name": reporter.get("name", "") if reporter else "",
                "email": reporter.get("email", "") if reporter else ""
            }
        })
    
    total = await db.reports.count_documents(filters)
    open_count = await db.reports.count_documents({"status": "OPEN"})
    
    return {
        "items": items,
        "total": total,
        "open_count": open_count,
        "page": page,
        "limit": limit
    }

@router.post("/{report_id}/resolve")
async def resolve_report(
    report_id: str,
    action: str = Query(..., description="delete_listing or dismiss"),
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    admin = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not admin or admin.get("role") != "ADMIN":
        raise HTTPException(403, "Chỉ admin mới có quyền xử lý báo cáo")
    
    if not _oid_ok(report_id):
        raise HTTPException(400, "ID báo cáo không hợp lệ")
    
    report = await db.reports.find_one({"_id": ObjectId(report_id)})
    if not report:
        raise HTTPException(404, "Không tìm thấy báo cáo")
    
    if action == "delete_listing":
        await db.listings.delete_one({"_id": report["listing_id"]})
        await db.reports.update_many(
            {"listing_id": report["listing_id"]},
            {"$set": {"status": "RESOLVED", "resolved_at": datetime.utcnow(), "resolved_by": ObjectId(x_user_id)}}
        )
        return {"ok": True, "message": "Đã xóa tin đăng và đóng tất cả báo cáo liên quan"}
    
    elif action == "dismiss":
        await db.reports.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {"status": "DISMISSED", "resolved_at": datetime.utcnow(), "resolved_by": ObjectId(x_user_id)}}
        )
        return {"ok": True, "message": "Đã bỏ qua báo cáo"}
    
    else:
        raise HTTPException(400, "Action phải là 'delete_listing' hoặc 'dismiss'")
