import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from database.models import Base
from database.database import engine
from sqlalchemy import text

def init_database():
    """Initialize database with PostGIS extension and all tables"""
    
    # Enable PostGIS only if using PostgreSQL
    if engine.dialect.name == "postgresql":
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
                conn.commit()
            print("[OK] PostGIS extension enabled")
        except Exception as e:
            print(f"[WARN] Could not enable PostGIS: {e}")
    else:
        print("[INFO] Using SQLite engine; skipping PostGIS extension.")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("[OK] Database initialized successfully!")
    print(f"[OK] Created/Verified {len(Base.metadata.tables)} tables")

if __name__ == "__main__":
    init_database()
