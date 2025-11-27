from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import get_db, close_db
from .routers import listings, auth, profiles, matching, favorites, reports, upload, analytics, connections, notifications
from .settings import settings

app = FastAPI(title="Trọ hub")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    db = await get_db()
    
    await db.listings.create_index([("location", "2dsphere")])
    await db.listings.create_index([("title", "text"), ("desc", "text")])
    await db.users.create_index("email", unique=True)
    await db.profiles.create_index([("user_id", 1)], unique=True)
    await db.profiles.create_index([("budget", 1)])
    await db.favorites.create_index([("user_id", 1), ("listing_id", 1)], unique=True)
    await db.reports.create_index([("listing_id", 1)])
    await db.connections.create_index([("from_user_id", 1), ("listing_id", 1)], unique=True)
    await db.connections.create_index([("to_user_id", 1)])
    await db.notifications.create_index([("user_id", 1), ("read", 1)])

@app.on_event("shutdown")
async def shutdown():
    await close_db()

app.include_router(listings.router)
app.include_router(auth.router)
app.include_router(profiles.router)
app.include_router(matching.router)
app.include_router(favorites.router)
app.include_router(reports.router)
app.include_router(upload.router)
app.include_router(analytics.router)
app.include_router(connections.router)
app.include_router(notifications.router)

@app.get("/healthz")
async def healthz():
    return {"ok": True}
