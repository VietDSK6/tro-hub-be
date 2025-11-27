from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from bson import ObjectId
from datetime import datetime
from ..db import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])

def _oid_ok(x: str) -> bool:
    return ObjectId.is_valid(x)

@router.get("")
async def get_notifications(
    page: int = 1,
    limit: int = 20,
    unread_only: bool = False,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    filters = {"user_id": ObjectId(x_user_id)}
    if unread_only:
        filters["read"] = False
    
    skip = (page - 1) * limit
    cursor = db.notifications.find(filters).sort("created_at", -1).skip(skip).limit(limit)
    
    items = []
    async for doc in cursor:
        items.append({
            "_id": str(doc["_id"]),
            "type": doc.get("type", ""),
            "title": doc.get("title", ""),
            "content": doc.get("content", ""),
            "metadata": doc.get("metadata", {}),
            "read": doc.get("read", False),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None
        })
    
    total = await db.notifications.count_documents(filters)
    unread_count = await db.notifications.count_documents({
        "user_id": ObjectId(x_user_id),
        "read": False
    })
    
    return {
        "items": items,
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "limit": limit
    }

@router.get("/unread-count")
async def get_unread_count(
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    count = await db.notifications.count_documents({
        "user_id": ObjectId(x_user_id),
        "read": False
    })
    return {"count": count}

@router.patch("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    if not _oid_ok(notification_id):
        raise HTTPException(400, "ID thông báo không hợp lệ")
    
    res = await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": ObjectId(x_user_id)},
        {"$set": {"read": True}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Không tìm thấy thông báo")
    
    return {"success": True}

@router.patch("/read-all")
async def mark_all_as_read(
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    await db.notifications.update_many(
        {"user_id": ObjectId(x_user_id), "read": False},
        {"$set": {"read": True}}
    )
    return {"success": True}

@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: str,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    if not _oid_ok(notification_id):
        raise HTTPException(400, "ID thông báo không hợp lệ")
    
    res = await db.notifications.delete_one({
        "_id": ObjectId(notification_id),
        "user_id": ObjectId(x_user_id)
    })
    if res.deleted_count == 0:
        raise HTTPException(404, "Không tìm thấy thông báo")
    
    return {"success": True}
