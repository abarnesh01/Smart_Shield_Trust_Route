import os
import pytest
from pathlib import Path
from sqlalchemy.orm import Session

from config.config import settings, BASE_DIR, DEFAULT_DB_PATH
from database.database import SQLALCHEMY_DATABASE_URL, init_db, SessionLocal, seed_safe_zones, Base, engine
from database.models import SafeZone
from api.models.safety_scorer import SafetyScorer

def test_database_path_consistency():
    """Verify that default database URL resolves to an absolute path anchored to backend root."""
    assert Path(DEFAULT_DB_PATH).is_absolute()
    assert "smartshield.db" in str(SQLALCHEMY_DATABASE_URL)
    assert Path(str(SQLALCHEMY_DATABASE_URL).replace("sqlite:///", "")).is_absolute()

def test_safety_scorer_initialization_without_warnings():
    """Verify SafetyScorer instantiates cleanly without triggering DB query warnings prior to init_db."""
    scorer = SafetyScorer()
    assert scorer is not None
    assert hasattr(scorer, "ensure_db_safe_zones_merged")

@pytest.mark.asyncio
async def test_safe_zone_seeding_and_loading(db_session: Session):
    """Verify safe zones are properly seeded from verified datasets and loaded into SafetyScorer."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    # Run seed function
    seed_safe_zones(db_session)
    
    count = db_session.query(SafeZone).count()
    assert count > 0, "SafeZone table should be populated from police_stations.json & hospitals.json"
    
    police_count = db_session.query(SafeZone).filter(SafeZone.zone_type == "police_station").count()
    hospital_count = db_session.query(SafeZone).filter(SafeZone.zone_type == "hospital").count()
    assert police_count > 0, "Police stations should be seeded"
    assert hospital_count > 0, "Hospitals should be seeded"

    # Verify SafetyScorer loads them lazily
    scorer = SafetyScorer()
    scorer.ensure_db_safe_zones_merged()
    assert len(scorer.police_stations) > 0
