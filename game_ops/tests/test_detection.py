"""
test_detection.py

Pure unit tests for the detection service.
No database or HTTP client needed — these test the logic functions directly.
"""

from services.detection import check_suspicious


def test_suspicious_player_high_kill_rate():
    """
    A player with 250 kills in a 60-second match should be flagged
    for an extremely high kill rate.
    """
    result = check_suspicious(
        {"kills": 250, "match_duration_seconds": 60, "score": 99000, "deaths": 0}
    )
    assert len(result) > 0
    assert any("Kill rate" in reason for reason in result)


def test_suspicious_player_score_rate():
    """
    A player with 99000 score in 60 seconds has a score rate of 1650/sec,
    far above the 100/sec threshold.
    """
    result = check_suspicious(
        {"kills": 5, "match_duration_seconds": 60, "score": 99000, "deaths": 2}
    )
    assert any("Score rate" in reason for reason in result)


def test_suspicious_short_match_duration():
    """
    A match lasting only 30 seconds is below the 120-second minimum
    and should trigger the duration flag.
    """
    result = check_suspicious(
        {"kills": 5, "match_duration_seconds": 30, "score": 500, "deaths": 2}
    )
    assert any("duration" in reason for reason in result)


def test_suspicious_kd_ratio():
    """
    A player with 25 kills and 0 deaths in a normal-length match
    should be flagged for suspicious K/D ratio.
    """
    result = check_suspicious(
        {"kills": 25, "deaths": 0, "score": 3000, "match_duration_seconds": 400}
    )
    assert any("K/D" in reason for reason in result)


def test_clean_player():
    """
    A player with reasonable stats should produce zero flag reasons.
    """
    result = check_suspicious(
        {"kills": 14, "deaths": 4, "score": 3200, "match_duration_seconds": 420}
    )
    assert result == []
