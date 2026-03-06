"""
routes_auth.py — Authentication routes for multi-restaurant login
"""
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import Restaurant

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    restaurant_id: int
    restaurant_name: str
    slug: str
    cuisine_type: str | None
    email: str


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    POST /api/auth/login
    Validates email + password against the restaurants table.
    Returns restaurant context (id, name, slug, etc.)
    """
    password_hash = hashlib.sha256(req.password.encode()).hexdigest()

    restaurant = db.query(Restaurant).filter(
        Restaurant.email == req.email,
        Restaurant.password_hash == password_hash,
        Restaurant.is_active == True,
    ).first()

    if not restaurant:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "slug": restaurant.slug,
        "cuisine_type": restaurant.cuisine_type,
        "email": restaurant.email,
    }


@router.get("/me/{restaurant_id}")
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db)):
    """
    GET /api/auth/me/{restaurant_id}
    Returns the restaurant profile.
    """
    restaurant = db.query(Restaurant).filter(
        Restaurant.id == restaurant_id,
        Restaurant.is_active == True,
    ).first()

    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    return {
        "restaurant_id": restaurant.id,
        "restaurant_name": restaurant.name,
        "slug": restaurant.slug,
        "cuisine_type": restaurant.cuisine_type,
        "email": restaurant.email,
        "phone": restaurant.phone,
        "address": restaurant.address,
    }
