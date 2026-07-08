"""Analyze endpoint — upload ảnh món ăn, trả về dinh dưỡng."""

from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.services.vision import identify_dish, VisionError

router = APIRouter(prefix="/api/v1", tags=["analyze"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/analyze")
async def analyze_food(file: UploadFile = File(...)):
    """Upload ảnh món ăn → nhận diện thành phần + ước lượng gram.

    Trả về:
        - dish_name: tên món
        - ingredients: danh sách {name, gram}
        - confidence: độ tự tin (0-1)
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file.content_type}. Chỉ chấp nhận JPEG, PNG, WebP.",
        )

    # Save temp file
    temp_path = UPLOAD_DIR / f"upload_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)

    try:
        result = await identify_dish(temp_path)
        return JSONResponse(content=result)
    except VisionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
