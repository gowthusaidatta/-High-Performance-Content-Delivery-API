from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from app.database import engine, Base
from app.models.asset import Asset, AssetVersion, AccessToken
from app.routes.assets import router as assets_router
from app.config import HOST, PORT, DEBUG

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="High-Performance Content Delivery API",
    description="A robust, high-performance content delivery API with edge caching",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(assets_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "High-Performance Content Delivery API",
        "docs": "/docs",
        "version": "1.0.0"
    }


def custom_openapi():
    """Customize OpenAPI schema."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="High-Performance Content Delivery API",
        version="1.0.0",
        description="A robust, high-performance content delivery API with edge caching",
        routes=app.routes,
    )
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT, debug=DEBUG)
