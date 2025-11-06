from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from bson import ObjectId
from ..db import get_db
from ..schemas import ReportIn

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("", status_code=201)
async def report_listing(payload: ReportIn, db = Depends(get_db), x_user_id: Optional[str] = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    listing_id = payload.listing_id
    reason = payload.reason.strip()
    if not listing_id or not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    if not reason:
        raise HTTPException(400, "Lý do báo cáo là bắt buộc")
    doc = {"listing_id": ObjectId(listing_id), "reporter_id": ObjectId(x_user_id), "reason": reason, "status": "OPEN"}
    await db.reports.insert_one(doc)
    return {"ok": True}
