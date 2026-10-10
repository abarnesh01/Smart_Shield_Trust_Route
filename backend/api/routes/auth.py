from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import User, RiderProfile, DriverProfile, UserSession
from api.schemas.auth import UserCreate, UserResponse, Token, UserLogin, TokenRefresh
from api.services.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from loguru import logger
import os
from datetime import datetime, timedelta
from api.utils.limiter import limiter
from config.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse)
@limiter.limit("5/minute")
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    """Register a new user (Rider or Driver publicly, Others via restricted paths)."""
    try:
        # 1. Check if registration is allowed for this role publicly
        allowed_public_roles = ["customer", "rider", "driver"]
        if user_in.role not in allowed_public_roles:
            admin_code = settings.ADMIN_REGISTRATION_CODE or os.getenv("ADMIN_REGISTRATION_CODE", "")
            if not admin_code or user_in.admin_code != admin_code:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Registration for role '{user_in.role}' requires a valid admin registration code."
                )

        # 2. Check if user already exists
        existing_user = db.query(User).filter(User.username == user_in.username).first()
        if existing_user:
            logger.warning(f"Registration failed: Username {user_in.username} already exists")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # 3. Handle status based on role
        user_status = "active"
        if user_in.role == "driver":
            user_status = "pending_approval"
        
        # 4. Create new user
        emergency_contacts = []
        if user_in.emergency_contact_name or user_in.emergency_contact_phone or user_in.emergency_contact_email:
            emergency_contacts.append({
                "name": user_in.emergency_contact_name,
                "phone": user_in.emergency_contact_phone,
                "email": user_in.emergency_contact_email
            })

        new_user = User(
            username=user_in.username,
            hashed_password=get_password_hash(user_in.password),
            role=user_in.role,
            full_name=user_in.full_name,
            phone=user_in.phone,
            email=user_in.email,
            status=user_status,
            emergency_contacts=emergency_contacts
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # 5. Create specific Profiles
        if new_user.role == "rider":
            rider_profile = RiderProfile(
                user_id=new_user.id,
                vehicle_type=user_in.vehicle_type,
                license_number=user_in.license_number,
                gender=user_in.gender,
                preferences=user_in.preferences or {}
            )
            db.add(rider_profile)
            db.commit()
        elif new_user.role == "driver":
            driver_profile = DriverProfile(
                user_id=new_user.id,
                license_number=user_in.license_number,
                vehicle_type=user_in.vehicle_type,
                vehicle_number=user_in.vehicle_number,
                documents=user_in.uploaded_documents or {}
            )
            db.add(driver_profile)
            db.commit()
        
        logger.info(f"New user registered: {new_user.username} (role: {new_user.role}, status: {new_user.status})")
        return new_user
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during registration: {str(e)}"
        )

@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, response: Response, user_in: UserLogin, db: Session = Depends(get_db)):
    """Login and status verification."""
    user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.username)
    ).first()
    
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if the logging in role matches the user's role
    if user_in.role and user.role != user_in.role:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unauthorized: This account is registered as a {user.role}, but you are trying to log in as a {user_in.role}."
        )

    # Status Checks
    if user.status == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account suspended. Please contact support."
        )
    
    if user.status == "pending_approval" and user.role == "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your application is under review. You will be notified once approved."
        )
    
    if user.status == "rejected" and user.role == "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your application was not approved. Please contact support for details."
        )
    
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status}"
        )
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    # Store session
    session = UserSession(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(session)
    db.commit()
    
    # Set HttpOnly Cookies
    cookie_secure = settings.COOKIE_SECURE or (settings.ENVIRONMENT.lower() == "production")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24 # 24 hours
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 7 # 7 days
    )
    
    logger.info(f"User logged in: {user.username} as {user.role}")
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name,
        "email": user.email
    }

@router.post("/refresh", response_model=Token)
@limiter.limit("5/minute")
def refresh(request: Request, response: Response, token_in: TokenRefresh, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    # Try to get refresh token from cookie first, then from request body
    refresh_token = request.cookies.get("refresh_token") or token_in.refresh_token
    
    session = db.query(UserSession).filter(UserSession.token == refresh_token).first()
    if not session or session.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user = db.query(User).filter(User.id == session.user_id).first()
    if not user:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    
    # Update Cookies
    cookie_secure = settings.COOKIE_SECURE or (settings.ENVIRONMENT.lower() == "production")
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure,
        samesite="lax",
        max_age=60 * 60 * 24
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "role": user.role
    }

@router.post("/logout")
def logout(request: Request, response: Response, token_in: TokenRefresh, db: Session = Depends(get_db)):
    """Logout and invalidate refresh token."""
    refresh_token = request.cookies.get("refresh_token") or token_in.refresh_token
    session = db.query(UserSession).filter(UserSession.token == refresh_token).first()
    if session:
        db.delete(session)
        db.commit()
    
    # Clear Cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    
    return {"message": "Logged out successfully"}
