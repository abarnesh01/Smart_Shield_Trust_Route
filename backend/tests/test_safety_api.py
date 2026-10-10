import pytest

# Test fixtures (client, db_session) are provided by conftest.py

def test_get_safety_heatmap(client, db_session):
    # Heatmap should work even without auth (public safety info)

    # Heatmap should work even without auth (public safety info)
    response = client.get(
        "/api/v1/safety/heatmap",
        params={
            "min_lat": 13.0,
            "min_lng": 80.0,
            "max_lat": 13.2,
            "max_lng": 80.3,
            "grid_size": 5
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "points" in data
    # CrimeDataService uses hardcoded TN districts if filters don't match or DB is empty
    assert len(data["points"]) > 0

def test_panic_button(client):
    # 1. Register and Login to get auth
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "panicuser",
            "password": "password",
            "role": "rider",
            "full_name": "Panic User",
            "phone": "1234567890",
            "email": "panic@example.com"
        },
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "panicuser", "password": "password", "role": "rider"}
    )
    cookies = login_res.cookies
    
    # 2. Trigger panic button
    response = client.post(
        "/api/v1/safety/panic-button",
        json={
            "rider_id": "panicuser",
            "location": {"latitude": 13.0827, "longitude": 80.2707}
        },
        cookies=cookies
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"
