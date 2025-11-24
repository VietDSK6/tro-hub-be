from fastapi import APIRouter, Depends, HTTPException
import bcrypt
import re
from bson import ObjectId
from ..db import get_db
from ..schemas import UserIn, LoginIn, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

def is_valid_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone: str) -> bool:
    pattern = r'^[0-9]{10,11}$'
    return re.match(pattern, phone.strip()) is not None

@router.post("/register", response_model=UserOut)
async def register(payload: UserIn, db = Depends(get_db)):
    """Register a new user account"""
    email = payload.email.strip().lower()
    
    if not email:
        raise HTTPException(400, detail="Email không được để trống")
    if not is_valid_email(email):
        raise HTTPException(400, detail="Định dạng email không hợp lệ")
    
    if not payload.password:
        raise HTTPException(400, detail="Mật khẩu không được để trống")
    if len(payload.password) < 6:
        raise HTTPException(400, detail="Mật khẩu phải có ít nhất 6 ký tự")
    
    if not payload.name or not payload.name.strip():
        raise HTTPException(400, detail="Họ tên không được để trống")
    
    if not payload.phone or not payload.phone.strip():
        raise HTTPException(400, detail="Số điện thoại không được để trống")
    if not is_valid_phone(payload.phone):
        raise HTTPException(400, detail="Số điện thoại không hợp lệ (10-11 chữ số)")
    
    existed = await db.users.find_one({"email": email})
    if existed:
        raise HTTPException(409, detail="Email này đã được đăng ký. Vui lòng đăng nhập.")
    
    pwd_hash = bcrypt.hashpw(payload.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    doc = {
        "email": email,
        "name": payload.name.strip(),
        "phone": payload.phone.strip(),
        "role": "USER",
        "password_hash": pwd_hash
    }
    res = await db.users.insert_one(doc)
    
    return UserOut(
        _id=str(res.inserted_id),
        email=email,
        name=payload.name.strip(),
        phone=payload.phone.strip(),
        role="USER"
    )

@router.post("/login", response_model=UserOut)
async def login(payload: LoginIn, db = Depends(get_db)):
    """Login with email and password"""
    email = payload.email.strip().lower()
    
    
    if not email:
        raise HTTPException(400, detail="Email không được để trống")
    if not payload.password:
        raise HTTPException(400, detail="Mật khẩu không được để trống")
    
    
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(401, detail="Không tìm thấy tài khoản với email này")
    
    if not user.get("password_hash"):
        raise HTTPException(401, detail="Tài khoản chưa thiết lập mật khẩu")
    
    if not bcrypt.checkpw(payload.password.encode('utf-8'), user["password_hash"].encode('utf-8')):
        raise HTTPException(401, detail="Mật khẩu không chính xác")
    
    return UserOut(
        _id=str(user["_id"]),
        email=user["email"],
        name=user.get("name", ""),
        phone=user.get("phone", ""),
        role=user.get("role", "USER")
    )
