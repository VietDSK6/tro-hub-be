from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Optional, Any, List
from bson import ObjectId
from ..db import get_db
from ..schemas import ReviewIn, ReviewOut, UserPreviewOut

router = APIRouter(prefix="/reviews", tags=["reviews"])

@router.post("", status_code=201, response_model=ReviewOut)
async def create_review(
    payload: ReviewIn,
    db = Depends(get_db),
    x_user_id: Optional[str] = Header(None)
):
    """Create a new review for a listing"""
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")
    listing_id = payload.listing_id
    if not listing_id or not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    scores = payload.scores or {}
    for k, v in list(scores.items()):
        try:
            scores[k] = float(v)
        except Exception:
            scores.pop(k, None)
    doc = {
        "listing_id": ObjectId(listing_id),
        "author_id": ObjectId(x_user_id),
        "scores": scores,
        "content": payload.content or "",
    }
    res = await db.reviews.insert_one(doc)
    saved = await db.reviews.find_one({"_id": res.inserted_id})
    
    review_out = ReviewOut(
        _id=str(saved["_id"]),
        listing_id=str(saved["listing_id"]),
        author_id=str(saved["author_id"]),
        scores=saved.get("scores", {}),
        content=saved.get("content", ""),
        created_at=saved.get("created_at")
    )
    
    # Fetch author info
    author = await db.users.find_one({"_id": saved["author_id"]})
    if author:
        review_out.author = UserPreviewOut(
            _id=str(author["_id"]),
            name=author.get("name", ""),
            email=author.get("email", ""),
            phone=author.get("phone", "")
        )
    
    return review_out

@router.get("", summary="List reviews by listing_id")
async def list_reviews(
    listing_id: str = Query(...),
    page: int = 1,
    limit: int = 20,
    db = Depends(get_db)
):
    """List all reviews for a specific listing with author info"""
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    skip = max(0, (page-1)*limit)
    cur = db.reviews.find({"listing_id": ObjectId(listing_id)}).skip(skip).limit(min(limit,100)).sort([("_id",-1)])
    items = []
    async for r in cur:
        review_out = ReviewOut(
            _id=str(r["_id"]),
            listing_id=str(r["listing_id"]),
            author_id=str(r["author_id"]),
            scores=r.get("scores", {}),
            content=r.get("content", ""),
            created_at=r.get("created_at")
        )
        
        # Fetch author info
        author = await db.users.find_one({"_id": r["author_id"]})
        if author:
            review_out.author = UserPreviewOut(
                _id=str(author["_id"]),
                name=author.get("name", ""),
                email=author.get("email", ""),
                phone=author.get("phone", "")
            )
        
        items.append(review_out.model_dump(by_alias=True))
    total = await db.reviews.count_documents({"listing_id": ObjectId(listing_id)})
    return {"items": items, "page": page, "limit": limit, "total": total}

@router.get("/summary", summary="Aggregate scores for a listing")
async def reviews_summary(listing_id: str = Query(...), db = Depends(get_db)):
    if not ObjectId.is_valid(listing_id):
        raise HTTPException(400, "listing_id không hợp lệ")
    pipeline = [
        {"$match": {"listing_id": ObjectId(listing_id)}},
        {"$project": {"scores": {"$objectToArray": "$scores"}}},
        {"$unwind": "$scores"},
        {"$group": {"_id": "$scores.k", "avg": {"$avg": "$scores.v"}, "count": {"$sum": 1}}},
        {"$project": {"metric": "$_id", "avg": {"$round": ["$avg", 2]}, "count": 1, "_id": 0}},
    ]
    metrics = [m async for m in db.reviews.aggregate(pipeline)]
    count = await db.reviews.count_documents({"listing_id": ObjectId(listing_id)})
    overall = round(sum(m["avg"] for m in metrics)/len(metrics), 2) if metrics else None
    return {"listing_id": listing_id, "count": count, "metrics": metrics, "overall": overall}
