from fastapi import APIRouter, Depends, HTTPException
import bcrypt
from bson import ObjectId
from ..db import get_db
from ..schemas import UserIn

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(payload: UserIn, db = Depends(get_db)):
    email = payload.email.strip().lower()
    if not email:
        raise HTTPException(400, "Email required")
    existed = await db.users.find_one({"email": email})
    if existed:
        raise HTTPException(409, "Email already registered")
    pwd_hash = bcrypt.hashpw(payload.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') if payload.password else ""
    doc = {"email": email, "name": payload.name or "", "password_hash": pwd_hash}
    res = await db.users.insert_one(doc)
    return {"_id": str(res.inserted_id), "email": email, "name": payload.name or ""}

@router.post("/login")
async def login(payload: UserIn, db = Depends(get_db)):
    email = payload.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash"):
        raise HTTPException(401, "Invalid credentials")
    if not bcrypt.checkpw(payload.password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        raise HTTPException(401, "Invalid credentials")
    return {"_id": str(user["_id"]), "email": user["email"], "name": user.get("name","")}
