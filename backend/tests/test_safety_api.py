import pytest

# Test fixtures (client, db_session) are provided by conftest.py

from database.models import PanicAlert

def test_get_safety_heatmap(client, db_session):
    # 1. Empty DB returns empty points list (no fabricated data)
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
    assert len(data["points"]) == 0

    # 2. Real incident in database returns real heatmap point
    alert = PanicAlert(
        rider_id="test_rider",
        location={"latitude": 13.08, "longitude": 80.27},
        status="active"
    )
    db_session.add(alert)
    db_session.commit()

    response_with_data = client.get(
        "/api/v1/safety/heatmap",
        params={
            "min_lat": 13.0,
            "min_lng": 80.0,
            "max_lat": 13.2,
            "max_lng": 80.3,
            "grid_size": 5
        }
    )
    assert response_with_data.status_code == 200
    points = response_with_data.json()["points"]
    assert len(points) == 1
    assert points[0]["lat"] == 13.08
    assert points[0]["lng"] == 80.27
    assert points[0]["intensity"] == 0.2

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
