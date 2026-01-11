"""
API routes initialization module.
Contains all route handlers and endpoint definitions.
"""

from fastapi import APIRouter
from app.routes.assets import router

__all__ = ["router"]
