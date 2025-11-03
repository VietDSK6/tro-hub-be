from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import get_db, close_db
from .routers import listings, auth, reviews, profiles, matching, favorites, reports, chat
from .settings import settings

app = FastAPI(title="Roommate Finder")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
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
    await db.reviews.create_index([( "listing_id", 1 )])
    await db.reviews.create_index([( "author_id", 1 )])
    await db.profiles.create_index([("user_id", 1)], unique=True)
    await db.profiles.create_index([("budget", 1)])
    await db.favorites.create_index([("user_id", 1), ("listing_id", 1)], unique=True)
    await db.messages.create_index([("room_id", 1), ("ts", 1)])
    await db.reports.create_index([("listing_id", 1)])

@app.on_event("shutdown")
async def shutdown():
    await close_db()

app.include_router(listings.router)
app.include_router(auth.router)
app.include_router(reviews.router)
app.include_router(profiles.router)
app.include_router(matching.router)
app.include_router(favorites.router)
app.include_router(reports.router)
app.include_router(chat.router)

@app.get("/healthz")
async def healthz():
    return {"ok": True}
