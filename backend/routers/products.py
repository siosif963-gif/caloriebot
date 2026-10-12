from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.deps import get_current_user
from schemas.product import ProductCreate, ProductOut, ProductSearchResponse
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
    result = product_service.search(db, query, user.id)
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
    return ProductOut.model_validate(product_service.get_by_id(db, product_id, user.id))


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProductOut:
    product = product_service.create_user_product(
        db,
        user.id,
        name=payload.name,
        brand=payload.brand,
        calories=payload.calories,
        protein=payload.protein,
        fat=payload.fat,
        carbs=payload.carbs,
    )
    return ProductOut.model_validate(product)


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    product_service.delete_user_product(db, user.id, product_id)
    return Response(status_code=204)
