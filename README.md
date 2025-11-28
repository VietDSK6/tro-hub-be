# Roommate Backend (FastAPI + MongoDB)

## Deploy to Railway.app (Free - Recommended)

### Prerequisites
1. Push code to GitHub repository
2. Create free Railway account at https://railway.app

### Deployment Steps
1. **Go to Railway Dashboard**: https://railway.app/new
2. **Deploy from GitHub repo**:
   - Click "Deploy from GitHub repo"
   - Select your `roommate-finder-be` repository
   - Railway auto-detects Python and uses `nixpacks.toml` config

3. **Add MongoDB Database**:
   - In your project, click "+ New"
   - Select "Database" → "Add MongoDB"
   - Railway automatically creates `MONGO_URL` variable

4. **Configure Environment Variables**:
   - Go to your service → Variables tab
   - Add these variables:
     - `MONGODB_URI`: `${{MongoDB.MONGO_URL}}` (reference to MongoDB service)
     - `MONGODB_DB`: `roommate`
     - `CLOUDINARY_CLOUD_NAME`: Your Cloudinary cloud name
     - `CLOUDINARY_API_KEY`: Your Cloudinary API key
     - `CLOUDINARY_API_SECRET`: Your Cloudinary API secret
     - `CORS_ORIGINS`: `https://yourapp.vercel.app,http://localhost:5173`
     - `SMTP_HOST`: SMTP server (e.g. smtp.gmail.com)
     - `SMTP_PORT`: 587
     - `SMTP_USER`: Your email address
     - `SMTP_PASS`: App password / SMTP password
     - `EMAIL_FROM`: Sender address shown in emails
     - `FRONTEND_URL`: URL of frontend for verification links

5. **Generate Domain**:
   - Go to Settings → Networking
   - Click "Generate Domain"
   - Your API will be live at: `https://your-app.up.railway.app`

6. **Share URL with team**: Copy the generated domain for frontend integration

**Free Tier**: $5 credit/month (~500 hours runtime), no sleep time, faster than Render!

## Quick start (Docker)
```bash
cd roommate-backend
cp .env.example .env
docker compose up --build
# API: http://localhost:8000/docs
# Mongo Express: http://localhost:8081  (user/pass: admin/admin)
```
## Local dev (no docker)
1. Start MongoDB locally (default: mongodb://localhost:27017)
2. Install deps and run:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
## Sample create & query
Create listing:
```bash
curl -X POST http://localhost:8000/listings -H "Content-Type: application/json" -d '{
  "title": "Phòng trọ Quận 3 có điều hòa",
  "desc": "Gần trường, an ninh tốt, có chỗ để xe",
  "price": 3500000,
  "area": 18,
  "amenities": ["ac","parking","water_heater"],
  "rules": {"pet": false, "cook": true},
  "images": ["https://example.com/1.jpg"],
  "location": {"type":"Point","coordinates":[106.682,10.78]}
}'
```
Query within 3km radius:
```bash
curl "http://localhost:8000/listings?lng=106.68&lat=10.78&radius_km=3&min_price=2500000&max_price=5000000"
```

## Auth (không dùng JWT – trả về user_id)
Đăng ký:
```bash
curl -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{
  "email": "demo@example.com",
  "password": "secret123",
  "name": "Demo User"
}'
```
Đăng nhập (trả về `_id`):
```bash
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{
  "email": "demo@example.com",
  "password": "secret123"
}'
```

## Email Verification
Gửi email xác thực (yêu cầu `X-User-Id`):
```bash
curl -X POST http://localhost:8000/auth/send-verification -H "X-User-Id: <USER_ID>"
```
Xác thực token (trả về từ liên kết email):
```bash
curl "http://localhost:8000/auth/verify?token=<TOKEN>"
```
Người dùng chưa xác thực email không thể đăng tin hoặc gửi yêu cầu kết nối.

## Listings (yêu cầu header `X-User-Id` cho create/patch/delete)
```bash
curl -X POST http://localhost:8000/listings   -H "Content-Type: application/json"   -H "X-User-Id: <USER_ID>"   -d '{
    "title":"Phòng trọ Q3",
    "desc":"Có máy lạnh",
    "price":3000000,
    "area":16,
    "amenities":["ac"],
    "location":{"type":"Point","coordinates":[106.682,10.78]}
  }'
```

## Reviews
Tạo review (dùng `X-User-Id` là người viết):
```bash
curl -X POST http://localhost:8000/reviews   -H "Content-Type: application/json"   -H "X-User-Id: <USER_ID>"   -d '{
    "listing_id":"<LISTING_ID>",
    "scores":{"security":4,"cleanliness":5,"utilities":4.5,"landlordAttitude":5},
    "content":"Phòng sạch, chủ thân thiện."
  }'
```
Lấy danh sách review theo listing:
```bash
curl "http://localhost:8000/reviews?listing_id=<LISTING_ID>&page=1&limit=10"
```
Tóm tắt điểm số:
```bash
curl "http://localhost:8000/reviews/summary?listing_id=<LISTING_ID>"
```

## Profiles
Tạo/cập nhật hồ sơ bản thân (yêu cầu `X-User-Id`):
```bash
curl -X PUT http://localhost:8000/profiles/me   -H "Content-Type: application/json" -H "X-User-Id: <USER_ID>"   -d '{"bio":"Sinh viên BK","budget":3000000,"habits":{"smoke":false,"pet":true,"cook":true},"location":{"type":"Point","coordinates":[106.682,10.78]}}'
```
Xem hồ sơ của mình:
```bash
curl -H "X-User-Id: <USER_ID>" http://localhost:8000/profiles/me
```

## Matching roommates
```bash
curl -H "X-User-Id: <USER_ID>" "http://localhost:8000/matching/roommates?top_k=10"
```

## Favorites
Thêm/lấy/xoá tin yêu thích:
```bash
curl -X POST http://localhost:8000/favorites -H "X-User-Id: <USER_ID>" -H "Content-Type: application/json" -d '{"listing_id":"<LISTING_ID>"}'
curl -H "X-User-Id: <USER_ID>" http://localhost:8000/favorites
curl -X DELETE -H "X-User-Id: <USER_ID>" "http://localhost:8000/favorites?listing_id=<LISTING_ID>"
```

## Reports (báo cáo tin vi phạm)
```bash
curl -X POST http://localhost:8000/reports -H "X-User-Id: <USER_ID>" -H "Content-Type: application/json" -d '{"listing_id":"<LISTING_ID>","reason":"Tin sai thông tin"}'
```

## Chat (WebSocket + history)
Kết nối WS (ví dụ bằng wscat):
```bash
# Terminal 1 (user A)
wscat -c "ws://localhost:8000/chat/ws?peer_id=<USER_B_ID>" -H "x-user-id: <USER_A_ID>"
# Terminal 2 (user B)
wscat -c "ws://localhost:8000/chat/ws?peer_id=<USER_A_ID>" -H "x-user-id: <USER_B_ID>"
# Gửi JSON: {"content":"hello"}
```
Lấy lịch sử:
```bash
curl -H "X-User-Id: <USER_A_ID>" "http://localhost:8000/chat/history?peer_id=<USER_B_ID>&page=1&limit=50"
```
