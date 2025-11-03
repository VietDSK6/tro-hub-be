# Roommate Backend (FastAPI + MongoDB)

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
