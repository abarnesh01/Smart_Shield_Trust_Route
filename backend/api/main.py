from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from api.routes import (
    delivery, safety, feedback, traffic, auth, 
    training, users, deliveries, tracking, 
    dashboard, monitoring, experiments, ai_reports, system,
    notifications, admin
)
from api.utils.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from config.config import settings
import os
from dotenv import load_dotenv

import time
from fastapi import FastAPI, APIRouter, Request
...
import sys
from loguru import logger
import sentry_sdk

load_dotenv()

# Configure Logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr, 
    level=settings.LOG_LEVEL
)
logger.add(
    settings.LOG_FILE, 
    rotation="10 MB", 
    retention="10 days", 
    level=settings.LOG_LEVEL,
    compression="zip"
)

# Configure Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=1.0 if settings.DEBUG else 0.1,
        profiles_sample_rate=1.0 if settings.DEBUG else 0.1,
    )
    logger.info("Sentry monitoring enabled.")

app = FastAPI(
    title="Smart Shield API",
    description="Backend API for Smart Shield Hospital Navigation and Safety Platform",
    version="1.0.0"
)

# Request Timing Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    # Use loguru for logging
    from loguru import logger
    logger.info(f"Request: {request.method} {request.url.path} - Process Time: {process_time:.4f}s")
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Add Limiter and Exception Handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create versioned router
api_v1_router = APIRouter(prefix="/api/v1")

# Register routes to the versioned router
api_v1_router.include_router(auth.router)
api_v1_router.include_router(delivery.router)
api_v1_router.include_router(deliveries.router)
api_v1_router.include_router(safety.router)
api_v1_router.include_router(feedback.router)
api_v1_router.include_router(traffic.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(training.router)
api_v1_router.include_router(tracking.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(monitoring.router)
api_v1_router.include_router(experiments.router)
api_v1_router.include_router(ai_reports.router)
api_v1_router.include_router(system.router)
api_v1_router.include_router(admin.router)

# Register the versioned router to the app
app.include_router(api_v1_router)

# Register notifications websocket at root level (as expected by frontend)
app.include_router(notifications.router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Smart Shield API",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.on_event("startup")
async def startup_event():
    """Run startup tasks like seeding the database."""
    import asyncio
    # Initialize database tables
    from database.database import init_db, SessionLocal
    from database.models import User
    from api.services.security import get_password_hash
    from api.routes.tracking import periodic_cache_cleanup

    await init_db()

    # Start background task: cleanup stale GPS cache entries every 60s
    asyncio.create_task(periodic_cache_cleanup())
    logger.info("📦 Location cache cleanup task started (runs every 60s)")

    # Safe development bootstrap (only when explicitly requested via environment)
    bootstrap_dev = (
        settings.ENVIRONMENT == "development" 
        and os.getenv("BOOTSTRAP_DEV_USERS", "false").lower() == "true"
    )
    if bootstrap_dev:
        db = SessionLocal()
        try:
            dev_configs = [
                ("DEV_ADMIN_USER", "admin@smartshield.com", "DEV_ADMIN_PASSWORD", "admin", "System Administrator"),
                ("DEV_DISPATCHER_USER", "dispatcher@smartshield.com", "DEV_DISPATCHER_PASSWORD", "dispatcher", "Emergency Dispatcher"),
                ("DEV_RIDER_USER", "rider@smartshield.com", "DEV_RIDER_PASSWORD", "rider", "Smart Rider"),
            ]
            for user_env, default_user, pwd_env, role, full_name in dev_configs:
                username = os.getenv(user_env, default_user)
                raw_pwd = os.getenv(pwd_env)
                if raw_pwd:
                    user = db.query(User).filter(User.username == username).first()
                    if not user:
                        logger.info(f"Bootstrapping dev user: {username} ({role})")
                        new_user = User(
                            username=username,
                            email=username,
                            hashed_password=get_password_hash(raw_pwd),
                            role=role,
                            full_name=full_name,
                            status="active"
                        )
                        db.add(new_user)
            db.commit()
        except Exception as e:
            logger.error(f"Error bootstrapping dev users: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

