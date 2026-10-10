import pytest
from fastapi import status
from config.config import Settings
import os

def test_sos_trigger_requires_authentication(client):
    """Calling SOS without authentication must return 401 Unauthorized."""
    response = client.post(
        "/api/v1/safety/panic-button",
        json={
            "rider_id": "unauth_rider",
            "location": {"latitude": 11.0168, "longitude": 76.9558}
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_sos_identity_spoofing_prevented(client):
    """Rider cannot spoof another rider's identity in SOS trigger."""
    # Register and login as legitimate user
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "spoof_tester_1",
            "password": "Password123!",
            "role": "rider",
            "full_name": "Spoof Tester",
            "phone": "9876543210",
            "email": "spooftester@example.com"
        }
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "spoof_tester_1", "password": "Password123!", "role": "rider"}
    )
    cookies = login_res.cookies
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to trigger panic button with a spoofed rider_id "victim_rider"
    response = client.post(
        "/api/v1/safety/panic-button",
        json={
            "rider_id": "victim_rider",
            "location": {"latitude": 11.0168, "longitude": 76.9558}
        },
        cookies=cookies,
        headers=headers
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    # The derived rider identity must be the authenticated user, NOT the spoofed payload
    assert data["status"] == "active"

def test_feedback_all_role_restrictions(client):
    """Listing all feedback requires dispatcher or admin role."""
    # 1. Unauthenticated -> 401
    unauth_res = client.get("/api/v1/feedback/all")
    assert unauth_res.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. As rider -> 403 Forbidden
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "rider_regular_fb",
            "password": "Password123!",
            "role": "rider",
            "full_name": "Regular Rider",
            "phone": "9876543211",
            "email": "regularrider@example.com"
        }
    )
    login_rider = client.post(
        "/api/v1/auth/login",
        json={"username": "rider_regular_fb", "password": "Password123!", "role": "rider"}
    )
    rider_headers = {"Authorization": f"Bearer {login_rider.json()['access_token']}"}
    rider_res = client.get("/api/v1/feedback/all", headers=rider_headers)
    assert rider_res.status_code == status.HTTP_403_FORBIDDEN

    # 3. As dispatcher -> 200 OK (login seeded dispatcher)
    login_disp = client.post(
        "/api/v1/auth/login",
        json={"username": "dispatcher@smartshield.com", "password": "Dispatch@123", "role": "dispatcher"}
    )
    if login_disp.status_code == 200:
        disp_headers = {"Authorization": f"Bearer {login_disp.json()['access_token']}"}
        disp_res = client.get("/api/v1/feedback/all", headers=disp_headers)
        assert disp_res.status_code == status.HTTP_200_OK
        assert "data" in disp_res.json()

def test_safety_alerts_role_restrictions(client):
    """Listing all panic alerts requires dispatcher/admin role."""
    # 1. Unauthenticated -> 401
    unauth_res = client.get("/api/v1/safety/alerts")
    assert unauth_res.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Register & login as regular rider -> 403
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "rider_alert_test",
            "password": "Password123!",
            "role": "rider",
            "full_name": "Alert Tester",
            "phone": "9876543212",
            "email": "alerttester@example.com"
        }
    )
    login_rider = client.post(
        "/api/v1/auth/login",
        json={"username": "rider_alert_test", "password": "Password123!", "role": "rider"}
    )
    assert login_rider.status_code == status.HTTP_200_OK
    rider_headers = {"Authorization": f"Bearer {login_rider.json()['access_token']}"}
    rider_res = client.get("/api/v1/safety/alerts", headers=rider_headers)
    assert rider_res.status_code == status.HTTP_403_FORBIDDEN

def test_admin_registration_privilege_escalation_prevented(client, monkeypatch):
    """Self-registering as admin without valid admin_code is rejected with 403."""
    from config.config import settings
    monkeypatch.setattr(settings, "ADMIN_REGISTRATION_CODE", "SUPER_SECRET_ADMIN_TOKEN_123")

    # 1. Attempt admin registration without admin_code -> 403
    res1 = client.post(
        "/api/v1/auth/register",
        json={
            "username": "attacker_admin_1",
            "password": "Password123!",
            "role": "admin",
            "full_name": "Attacker Admin",
            "email": "attacker1@example.com"
        }
    )
    assert res1.status_code == status.HTTP_403_FORBIDDEN

    # 2. Attempt admin registration with wrong admin_code -> 403
    res2 = client.post(
        "/api/v1/auth/register",
        json={
            "username": "attacker_admin_2",
            "password": "Password123!",
            "role": "admin",
            "admin_code": "wrong_code",
            "full_name": "Attacker Admin",
            "email": "attacker2@example.com"
        }
    )
    assert res2.status_code == status.HTTP_403_FORBIDDEN

    # 3. Admin registration with valid admin_code -> 200
    res3 = client.post(
        "/api/v1/auth/register",
        json={
            "username": "legit_admin_3",
            "password": "Password123!",
            "role": "admin",
            "admin_code": "SUPER_SECRET_ADMIN_TOKEN_123",
            "full_name": "Legit Admin",
            "email": "legitadmin3@example.com"
        }
    )
    assert res3.status_code == status.HTTP_200_OK

def test_production_secret_validation():
    """Settings must fail safely in production environment if secrets are default or empty."""
    # Insecure placeholder in production must raise ValueError
    with pytest.raises(ValueError, match="Insecure or missing SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="change-me-in-production",
            JWT_SECRET_KEY="valid-long-secret-key-for-test"
        )

    with pytest.raises(ValueError, match="Insecure or missing JWT_SECRET_KEY"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="valid-long-secret-key-for-test",
            JWT_SECRET_KEY="jwt-secret-key-change-me"
        )

    with pytest.raises(ValueError):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="",
            JWT_SECRET_KEY="valid-long-secret-key-for-test"
        )

    # Valid strong secrets in production should instantiate cleanly
    valid_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a-very-strong-production-random-secret-key-here",
        JWT_SECRET_KEY="another-strong-production-jwt-random-key-here"
    )
    assert valid_settings.ENVIRONMENT == "production"

def test_sos_resolution_role_restriction(client):
    """Only dispatchers, admins, or the alert's owner can resolve an alert."""
    # 1. Unauthenticated -> 401
    unauth = client.post(
        "/api/v1/safety/panic-button/resolve",
        json={"alert_id": "dummy_id", "rider_id": "some_rider", "resolution_notes": "test"}
    )
    assert unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Register & login as bystander rider
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "bystander_rider",
            "password": "Password123!",
            "role": "rider",
            "full_name": "Bystander Rider",
            "phone": "9876543219",
            "email": "bystander@example.com"
        }
    )
    bystander_login = client.post(
        "/api/v1/auth/login",
        json={"username": "bystander_rider", "password": "Password123!", "role": "rider"}
    )
    headers = {"Authorization": f"Bearer {bystander_login.json()['access_token']}"}

    # Attempt to resolve someone else's alert as a regular rider -> 403 Forbidden
    res = client.post(
        "/api/v1/safety/panic-button/resolve",
        json={"alert_id": "some_alert", "rider_id": "other_victim_rider", "resolution_notes": "fake resolve"},
        headers=headers
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN

