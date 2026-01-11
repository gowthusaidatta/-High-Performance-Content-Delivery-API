#!/usr/bin/env python3
"""
Database initialization script for the Content Delivery API.
Creates all necessary tables and initializes the database.
"""

import sys
from app.database import engine, Base
from app.models.asset import Asset, AssetVersion, AccessToken

def init_db():
    """Initialize the database by creating all tables."""
    print("Initializing database...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ Database initialized successfully")
        print("✓ Created tables: assets, asset_versions, access_tokens")
        return True
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return False

if __name__ == "__main__":
    success = init_db()
    sys.exit(0 if success else 1)
