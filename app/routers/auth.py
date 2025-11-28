from fastapi import APIRouter, Depends, HTTPException, Header
import bcrypt
import re
import secrets
from datetime import datetime
from bson import ObjectId
from ..db import get_db
from ..schemas import UserIn, LoginIn, UserOut
from ..utils.email import send_email
from ..settings import settings

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
        role="USER",
        is_verified=False
    )


@router.post("/send-verification")
async def send_verification_email(db = Depends(get_db), x_user_id: str | None = Header(None)):
    if not x_user_id or not ObjectId.is_valid(x_user_id):
        raise HTTPException(401, "Thiếu hoặc không hợp lệ X-User-Id")

    user = await db.users.find_one({"_id": ObjectId(x_user_id)})
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")
    if user.get("is_verified"):
        return {"sent": False, "message": "Tài khoản đã được xác thực"}

    token = secrets.token_urlsafe(32)
    now_iso = datetime.utcnow().isoformat()
    await db.users.update_one({"_id": ObjectId(x_user_id)}, {"$set": {"verification_token": token, "verification_sent_at": now_iso}})

    verify_url = f"{settings.frontend_url.rstrip('/')}/auth/verify?token={token}"
    subject = "Xác thực email - Trọ Hub"
    body = f"Xin chào {user.get('name','')},\n\nVui lòng bấm vào liên kết sau để xác thực địa chỉ email của bạn:\n{verify_url}\n\nNếu bạn không yêu cầu xác thực, hãy bỏ qua email này."
    await send_email(user.get("email"), subject, body)

    return {"sent": True, "message": "Email xác thực đã được gửi"}


@router.get("/verify")
async def verify_token(token: str, db = Depends(get_db)):
    if not token:
        raise HTTPException(400, "Token không hợp lệ")
    user = await db.users.find_one({"verification_token": token})
    if not user:
        raise HTTPException(404, "Token không hợp lệ hoặc đã hết hạn")

    await db.users.update_one({"_id": user["_id"]}, {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}})
    return {"verified": True, "message": "Email đã được xác thực"}

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
        role=user.get("role", "USER"),
        is_verified=user.get("is_verified", False)
    )
