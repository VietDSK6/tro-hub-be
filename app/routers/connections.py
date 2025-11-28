from fastapi import APIRouter, Depends, HTTPException, Header, Query
from typing import Optional
from bson import ObjectId
from datetime import datetime
from ..db import get_db
from ..utils.email import send_email
from ..settings import settings

router = APIRouter(prefix="/connections", tags=["connections"])

def _oid_ok(x: str) -> bool:
    return ObjectId.is_valid(x)

@router.post("", status_code=201)
async def create_connection(
    listing_id: str,
    message: str = "",
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    # require verified user
    from_user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not from_user:
        raise HTTPException(401, "Không tìm thấy người dùng")
    if not from_user.get("is_verified"):
        raise HTTPException(403, "Bạn cần xác thực email trước khi gửi yêu cầu kết nối")
    if not _oid_ok(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    
    listing = await db.listings.find_one({"_id": ObjectId(listing_id)})
    if not listing:
        raise HTTPException(404, "Không tìm thấy tin đăng")
    
    to_user_id = listing["owner_id"]
    
    if str(to_user_id) == x_user_id:
        raise HTTPException(400, "Không thể kết nối với chính mình")
    
    existing = await db.connections.find_one({
        "from_user_id": ObjectId(x_user_id),
        "listing_id": ObjectId(listing_id)
    })
    if existing:
        raise HTTPException(400, "Bạn đã gửi yêu cầu kết nối cho tin đăng này")
    
    doc = {
        "from_user_id": ObjectId(x_user_id),
        "to_user_id": to_user_id,
        "listing_id": ObjectId(listing_id),
        "message": message,
        "status": "PENDING",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    res = await db.connections.insert_one(doc)
    
    from_user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    from_name = from_user.get("name", "Người dùng") if from_user else "Người dùng"
    
    notification = {
        "user_id": to_user_id,
        "type": "CONNECTION_REQUEST",
        "title": "Yêu cầu kết nối mới",
        "content": f"{from_name} muốn liên hệ về phòng trọ '{listing.get('title', '')}'",
        "metadata": {
            "connection_id": str(res.inserted_id),
            "listing_id": listing_id,
            "from_user_id": x_user_id
        },
        "read": False,
        "created_at": datetime.utcnow()
    }
    await db.notifications.insert_one(notification)
    # send optional email to owner
    try:
        owner_email = listing.get("email")
        if owner_email:
            subject = "Yêu cầu kết nối mới trên Trọ Hub"
            body = f"{from_name} đã gửi yêu cầu kết nối về phòng '{listing.get('title','')}'.\n\nTin nhắn: {message}\n\nMở ứng dụng để xem chi tiết."
            await send_email(owner_email, subject, body)
    except Exception:
        pass
    
    return {
        "_id": str(res.inserted_id),
        "status": "PENDING",
        "message": "Đã gửi yêu cầu kết nối"
    }

@router.get("/outgoing")
async def get_outgoing_connections(
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    skip = (page - 1) * limit
    cursor = db.connections.find({"from_user_id": ObjectId(x_user_id)}).sort("created_at", -1).skip(skip).limit(limit)
    
    items = []
    async for doc in cursor:
        listing = await db.listings.find_one({"_id": doc["listing_id"]})
        to_user = await db.users.find_one({"_id": doc["to_user_id"]})
        
        item = {
            "_id": str(doc["_id"]),
            "listing_id": str(doc["listing_id"]),
            "to_user_id": str(doc["to_user_id"]),
            "message": doc.get("message", ""),
            "status": doc["status"],
            "created_at": doc["created_at"].isoformat(),
            "listing": {
                "_id": str(listing["_id"]),
                "title": listing.get("title", ""),
                "price": listing.get("price", 0),
                "images": listing.get("images", [])
            } if listing else None,
            "to_user": {
                "name": to_user.get("name", ""),
                "email": to_user.get("email", "") if doc["status"] == "ACCEPTED" else None,
                "phone": to_user.get("phone", "") if doc["status"] == "ACCEPTED" else None
            } if to_user else None
        }
        items.append(item)
    
    total = await db.connections.count_documents({"from_user_id": ObjectId(x_user_id)})
    return {"items": items, "total": total, "page": page, "limit": limit}

@router.get("/incoming")
async def get_incoming_connections(
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    
    skip = (page - 1) * limit
    cursor = db.connections.find({"to_user_id": ObjectId(x_user_id)}).sort("created_at", -1).skip(skip).limit(limit)
    
    items = []
    async for doc in cursor:
        listing = await db.listings.find_one({"_id": doc["listing_id"]})
        from_user = await db.users.find_one({"_id": doc["from_user_id"]})
        
        item = {
            "_id": str(doc["_id"]),
            "listing_id": str(doc["listing_id"]),
            "from_user_id": str(doc["from_user_id"]),
            "message": doc.get("message", ""),
            "status": doc["status"],
            "created_at": doc["created_at"].isoformat(),
            "listing": {
                "_id": str(listing["_id"]),
                "title": listing.get("title", ""),
                "price": listing.get("price", 0),
                "images": listing.get("images", [])
            } if listing else None,
            "from_user": {
                "name": from_user.get("name", ""),
                "email": from_user.get("email", ""),
                "phone": from_user.get("phone", "")
            } if from_user else None
        }
        items.append(item)
    
    total = await db.connections.count_documents({"to_user_id": ObjectId(x_user_id)})
    return {"items": items, "total": total, "page": page, "limit": limit}

@router.patch("/{connection_id}")
async def update_connection_status(
    connection_id: str,
    status: str = Query(..., description="ACCEPTED or REJECTED"),
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    if not _oid_ok(connection_id):
        raise HTTPException(400, "ID kết nối không hợp lệ")
    if status not in ["ACCEPTED", "REJECTED"]:
        raise HTTPException(400, "Status phải là ACCEPTED hoặc REJECTED")
    
    conn = await db.connections.find_one({
        "_id": ObjectId(connection_id),
        "to_user_id": ObjectId(x_user_id)
    })
    if not conn:
        raise HTTPException(404, "Không tìm thấy yêu cầu kết nối")
    
    if conn["status"] != "PENDING":
        raise HTTPException(400, "Yêu cầu này đã được xử lý")
    
    await db.connections.update_one(
        {"_id": ObjectId(connection_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )
    
    to_user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    to_name = to_user.get("name", "Chủ phòng") if to_user else "Chủ phòng"
    listing = await db.listings.find_one({"_id": conn["listing_id"]})
    listing_title = listing.get("title", "") if listing else ""
    
    if status == "ACCEPTED":
        notification = {
            "user_id": conn["from_user_id"],
            "type": "CONNECTION_ACCEPTED",
            "title": "Yêu cầu kết nối được chấp nhận",
            "content": f"{to_name} đã chấp nhận yêu cầu kết nối của bạn về phòng trọ '{listing_title}'",
            "metadata": {
                "connection_id": connection_id,
                "listing_id": str(conn["listing_id"]),
                "to_user_id": x_user_id
            },
            "read": False,
            "created_at": datetime.utcnow()
        }
    else:
        notification = {
            "user_id": conn["from_user_id"],
            "type": "CONNECTION_REJECTED",
            "title": "Yêu cầu kết nối bị từ chối",
            "content": f"Yêu cầu kết nối của bạn về phòng trọ '{listing_title}' đã bị từ chối",
            "metadata": {
                "connection_id": connection_id,
                "listing_id": str(conn["listing_id"])
            },
            "read": False,
            "created_at": datetime.utcnow()
        }
    await db.notifications.insert_one(notification)
    # send email notification to requester
    try:
        from_user_doc = await db.users.find_one({"_id": conn["from_user_id"]})
        if from_user_doc and from_user_doc.get("email"):
            subj = "Yêu cầu kết nối đã được chấp nhận"
            body = f"{to_name} đã chấp nhận yêu cầu kết nối của bạn về phòng '{listing_title}'.\n\nBạn có thể liên hệ: {to_user.get('phone','')}"
            await send_email(from_user_doc.get("email"), subj, body)
    except Exception:
        pass
    
    return {"status": status, "message": "Đã cập nhật trạng thái"}

@router.get("/check/{listing_id}")
async def check_connection(
    listing_id: str,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    if not _oid_ok(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    
    conn = await db.connections.find_one({
        "from_user_id": ObjectId(x_user_id),
        "listing_id": ObjectId(listing_id)
    })
    
    if not conn:
        return {"connected": False, "status": None}
    
    result = {
        "connected": True,
        "status": conn["status"],
        "connection_id": str(conn["_id"])
    }
    
    if conn["status"] == "ACCEPTED":
        listing = await db.listings.find_one({"_id": ObjectId(listing_id)})
        if listing:
            owner = await db.users.find_one({"_id": listing["owner_id"]})
            if owner:
                result["owner_contact"] = {
                    "name": owner.get("name", ""),
                    "email": owner.get("email", ""),
                    "phone": owner.get("phone", "")
                }
    
    return result

@router.get("/listing/{listing_id}")
async def get_connections_by_listing(
    listing_id: str,
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    if not x_user_id or not _oid_ok(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    if not _oid_ok(listing_id):
        raise HTTPException(400, "ID tin đăng không hợp lệ")
    
    listing = await db.listings.find_one({"_id": ObjectId(listing_id)})
    if not listing:
        raise HTTPException(404, "Không tìm thấy tin đăng")
    
    if str(listing["owner_id"]) != x_user_id:
        raise HTTPException(403, "Bạn không có quyền xem yêu cầu kết nối của tin đăng này")
    
    skip = (page - 1) * limit
    cursor = db.connections.find({"listing_id": ObjectId(listing_id)}).sort("created_at", -1).skip(skip).limit(limit)
    
    items = []
    async for doc in cursor:
        from_user = await db.users.find_one({"_id": doc["from_user_id"]})
        from_profile = await db.profiles.find_one({"user_id": doc["from_user_id"]})
        
        item = {
            "_id": str(doc["_id"]),
            "listing_id": str(doc["listing_id"]),
            "from_user_id": str(doc["from_user_id"]),
            "message": doc.get("message", ""),
            "status": doc["status"],
            "created_at": doc["created_at"].isoformat(),
            "from_user": {
                "name": from_user.get("name", "") if from_user else "",
                "email": from_user.get("email", "") if from_user else "",
                "phone": from_user.get("phone", "") if from_user else "",
            } if from_user else None,
            "from_profile": {
                "full_name": from_profile.get("full_name", "") if from_profile else "",
                "avatar": from_profile.get("avatar", "") if from_profile else "",
                "budget": from_profile.get("budget", 0) if from_profile else 0,
            } if from_profile else None
        }
        items.append(item)
    
    total = await db.connections.count_documents({"listing_id": ObjectId(listing_id)})
    pending_count = await db.connections.count_documents({"listing_id": ObjectId(listing_id), "status": "PENDING"})
    
    return {
        "items": items,
        "total": total,
        "pending_count": pending_count,
        "page": page,
        "limit": limit
    }
