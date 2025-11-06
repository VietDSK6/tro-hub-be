from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import cloudinary
import cloudinary.uploader
from ..settings import settings

router = APIRouter(prefix="/upload", tags=["upload"])

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret
)

@router.post("/images")
async def upload_images(files: List[UploadFile] = File(...)):
    if not settings.cloudinary_cloud_name:
        raise HTTPException(400, "Cloudinary chưa được cấu hình")
    
    if len(files) > 10:
        raise HTTPException(400, "Tối đa 10 ảnh mỗi lần tải")
    
    uploaded_urls = []
    
    for file in files:
        
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(400, f"File {file.filename} không phải là ảnh")
        
        
        try:
            contents = await file.read()
            result = cloudinary.uploader.upload(
                contents,
                folder="roommate-listings",
                resource_type="image",
                quality="auto",
                fetch_format="auto"
            )
            uploaded_urls.append(result["secure_url"])
        except Exception as e:
            raise HTTPException(500, f"Lỗi tải ảnh {file.filename}: {str(e)}")
    
    return {"urls": uploaded_urls}
