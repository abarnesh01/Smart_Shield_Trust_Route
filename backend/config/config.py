"""Configuration settings for the application."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "smartshield.db"

class Settings(BaseSettings):
    """Application settings."""
    
    # Project Info
    PROJECT_NAME: str = "AI Smart Shield Trust Route"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{DEFAULT_DB_PATH}"  # Default to absolute SQLite path for backend
    )
    
    # API Keys
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    GRAPHHOPPER_API_KEY: str = os.getenv("GRAPHHOPPER_API_KEY", "")
    MAPBOX_TOKEN: str = os.getenv("MAPBOX_TOKEN", "")
    SAFEGRAPH_API_KEY: str = os.getenv("SAFEGRAPH_API_KEY", "")
    POSITIONSTACK_API_KEY: str = os.getenv("POSITIONSTACK_API_KEY", "")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "jwt-secret-key-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
    ]
    
    # Server
    HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Route Optimization
    MAX_DELIVERY_STOPS: int = 50
    OPTIMIZATION_ALGORITHM: str = os.getenv("OPTIMIZATION_ALGORITHM", "astar")  # astar, hybrid, genetic, nearest_neighbor
    
    # Safety Scoring
    SAFETY_WEIGHTS: dict = {
        "infrastructure_proximity": 0.35,  # Distance to police/hospital
        "lighting": 0.30,
        "patrol_presence": 0.20,
        "traffic_safety": 0.10,
        "user_feedback": 0.05
    }
    
    # Time Windows
    DEFAULT_TIME_WINDOW_MINUTES: int = 15
    
    # Fuel Efficiency
    FUEL_CONSUMPTION_PER_KM: float = 0.085  # liters per km (average for delivery vehicles)
    
    # Maps & Geocoding
    MAX_GEOCODE_RETRIES: int = 3
    GEOCODE_CACHE_TTL: int = 3600  # seconds
    
    # ML Models
    MODEL_CACHE_DIR: Path = Path("models/cache")
    SAFETY_MODEL_PATH: str = "api/models/saved_models/safety_scorer_rf.pkl"
    SAFETY_SCALER_PATH: str = "models/safety_scaler.pkl"
    HOSPITALS_DATA_PATH: str = "data/hospitals.json"
    
    # Feedback System
    MIN_FEEDBACK_SAMPLES: int = 5  # Minimum samples before retraining
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # Email Configuration (for SOS alerts)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "dharunikaktm@gmail.com")
    EMERGENCY_EMAIL: str = os.getenv("EMERGENCY_EMAIL", "dharunikaktm@gmail.com")

    # Twilio Configuration (for SMS alerts)
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    EMERGENCY_PHONE: str = os.getenv("EMERGENCY_PHONE", "") # Admin/Emergency contact phone
    
    # Monitoring (Sentry)
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    
    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "case_sensitive": True,
        "extra": "ignore"
    }

# Create global settings instance
settings = Settings()

# Ensure directories exist
settings.MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(parents=True, exist_ok=True)

