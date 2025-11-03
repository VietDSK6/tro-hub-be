from typing import Any, Dict

def build_pagination(page: int = 1, limit: int = 20) -> Dict[str, Any]:
    page = max(1, int(page or 1))
    limit = max(1, min(int(limit or 20), 100))
    skip = (page - 1) * limit
    return {"page": page, "limit": limit, "skip": skip}
