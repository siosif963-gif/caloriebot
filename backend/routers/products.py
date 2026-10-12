from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.deps import get_current_user
from schemas.product import ProductOut, ProductSearchResponse
from services import product_service
from services.errors import ValidationError

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/search", response_model=ProductSearchResponse)
def search_products(
    q: str = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductSearchResponse:
    query = q.strip()
    if not 2 <= len(query) <= 100:
        raise ValidationError("Некорректные данные: q — длина запроса от 2 до 100 символов")
    result = product_service.search(db, query)
    return ProductSearchResponse(
        items=[ProductOut.model_validate(p) for p in result.items],
        external_status=result.external_status,  # type: ignore[arg-type]
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductOut:
    return ProductOut.model_validate(product_service.get_by_id(db, product_id))
