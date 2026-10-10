"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import StaticPool
import sys
from pathlib import Path
from datetime import datetime, UTC

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config.config import settings
from loguru import logger

BASE_DIR = Path(__file__).resolve().parent.parent

# Database URL
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Normalize relative SQLite paths to backend directory
if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///./"):
    db_filename = SQLALCHEMY_DATABASE_URL.replace("sqlite:///./", "", 1)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{BASE_DIR / db_filename}"
elif SQLALCHEMY_DATABASE_URL.startswith("sqlite:///") and not SQLALCHEMY_DATABASE_URL.startswith("sqlite:////") and SQLALCHEMY_DATABASE_URL != "sqlite://":
    # Handles relative path like sqlite:///smartshield.db
    db_filename = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "", 1)
    if not Path(db_filename).is_absolute():
        SQLALCHEMY_DATABASE_URL = f"sqlite:///{BASE_DIR / db_filename}"

# Handle Render's 'postgres://' format which SQLAlchemy needs as 'postgresql://'
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Create engine
# Use static pool for SQLite, connection pooling for PostgreSQL
if "sqlite" in SQLALCHEMY_DATABASE_URL.lower():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def seed_safe_zones(db: Session):
    """Seed safe zones from verified JSON datasets if table is empty."""
    from database.models import SafeZone
    import json
    
    try:
        count = db.query(SafeZone).count()
        if count > 0:
            return
        
        police_file = BASE_DIR / "data" / "police_stations.json"
        hospitals_file = BASE_DIR / "data" / "hospitals.json"
        
        seeded = 0
        if police_file.exists():
            with open(police_file, "r", encoding="utf-8") as f:
                police_list = json.load(f)
                for item in police_list:
                    sz = SafeZone(
                        zone_type="police_station",
                        name=item.get("name"),
                        location={"latitude": item.get("latitude"), "longitude": item.get("longitude")},
                        address=item.get("address"),
                        phone=item.get("phone"),
                        is_24hr=True,
                        safety_score=95.0
                    )
                    db.add(sz)
                    seeded += 1
                    
        if hospitals_file.exists():
            with open(hospitals_file, "r", encoding="utf-8") as f:
                hospitals_list = json.load(f)
                for item in hospitals_list:
                    sz = SafeZone(
                        zone_type="hospital",
                        name=item.get("name"),
                        location={"latitude": item.get("latitude"), "longitude": item.get("longitude")},
                        address=item.get("address"),
                        phone=item.get("phone"),
                        is_24hr=True,
                        safety_score=90.0
                    )
                    db.add(sz)
                    seeded += 1
                    
        if seeded > 0:
            db.commit()
            logger.info(f"Seeded {seeded} verified safe zones from datasets into database")
    except Exception as e:
        logger.error(f"Error seeding safe zones: {e}")
        db.rollback()


async def init_db():
    """Initialize database tables."""
    try:
        # Import all models here to ensure they're registered
        from database.models import Route, SafetyFeedback, SafetyScore, DeliveryCompany, Rider, DeliveryStatus, RouteMonitoring, PanicAlert, RiderCheckIn, SafeZone, RideAlong, User, DeliveryRoute, RouteSegment, DeliveryFeedback, HistoricalDelivery, CrowdsourcedAlert, RiderProfile, DriverProfile, UserSession, Delivery, DeliveryBatch, DeliveryProof, Customer, BuddyPair
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified successfully")
        
        # Seed safe zones if empty
        db = SessionLocal()
        try:
            seed_safe_zones(db)
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        # In development, we can work without database
        if settings.DEBUG:
            logger.warning("Continuing without database connection")
        else:
            raise


def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
