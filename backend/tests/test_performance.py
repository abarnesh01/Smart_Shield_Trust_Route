import pytest
import time
from api.models.safety_scorer import SafetyScorer
from api.services.maps import MapsService
from api.schemas.delivery import Coordinate

def test_safety_scorer_performance():
    scorer = SafetyScorer()
    coord = Coordinate(latitude=13.0827, longitude=80.2707)
    
    start_time = time.time()
    score1, factors1 = scorer.score_location(coord)
    first_duration = time.time() - start_time
    
    start_time = time.time()
    score2, factors2 = scorer.score_location(coord)
    second_duration = time.time() - start_time
    
    assert score1 == score2
    assert first_duration < 2.0
    assert second_duration < 1.0

def test_maps_service_initialization_performance():
    start_time = time.time()
    service = MapsService()
    duration = time.time() - start_time
    assert service is not None
    assert duration < 1.0
