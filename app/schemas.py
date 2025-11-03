from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

class Location(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: List[float] = Field(..., min_length=2, max_length=2, description="[lng, lat]")

class ListingIn(BaseModel):
    title: str
    desc: str = ""
    price: float = 0
    area: float = 0
    amenities: List[str] = []
    rules: dict = {}
    images: List[str] = []
    video: Optional[str] = None
    status: Literal["ACTIVE","HIDDEN","RENTED"] = "ACTIVE"
    location: Location

class Listing(ListingIn):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    owner_id: PyObjectId

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, json_encoders={ObjectId: str})

class ListingOut(ListingIn):
    id: str = Field(alias="_id")
    owner_id: str

class ListingPatch(BaseModel):
    title: Optional[str] = None
    desc: Optional[str] = None
    price: Optional[float] = None
    area: Optional[float] = None
    amenities: Optional[List[str]] = None
    rules: Optional[dict] = None
    images: Optional[List[str]] = None
    video: Optional[str] = None
    status: Optional[Literal["ACTIVE","HIDDEN","RENTED"]] = None
    location: Optional[Location] = None

class UserIn(BaseModel):
    email: str
    password: str
    name: Optional[str] = ""

class User(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    email: str
    name: Optional[str] = ""
    password_hash: str

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True, json_encoders={ObjectId: str})

class UserOut(BaseModel):
    id: str = Field(alias="_id")
    email: str
    name: Optional[str] = ""

class ReviewIn(BaseModel):
    listing_id: str
    scores: dict = Field(default_factory=dict, description="e.g. {security, cleanliness, utilities, landlordAttitude} with 1-5")
    content: str = ""

class ReviewOut(BaseModel):
    id: str = Field(alias="_id")
    listing_id: str
    author_id: str
    scores: dict
    content: str
    created_at: Optional[str] = None
