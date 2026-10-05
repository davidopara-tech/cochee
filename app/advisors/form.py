"""Form advisor: scores how well each player is playing right now."""

from sqlalchemy import select

from app.advisors.common import min_max, scale, weighted_score
from app.models import Player

WEIGHTS = {
    "form": 0.40,
    "event_points": 0.25,
    "ppg": 0.15,
    "xgi90": 0.15,
    "minutes": 0.05,
}


def _raw_features(player: Player) -> dict[str, float]:
    """Pulls the five raw inputs from a Player row."""
    return {
        "form": player.form or 0.0,
        "event_points": float(player.event_points or 0),
        "ppg": player.points_per_game or 0.0,
        "xgi90": player.expected_goal_involvements_per_90 or 0.0,
        "minutes": float(player.minutes or 0),
    }


def get_form_scores(db) -> dict[int, float]:
    """Returns {player_id: form_score} where score is 0-10."""
    players = db.scalars(select(Player)).all()
    raw = {p.id: _raw_features(p) for p in players}

    bounds = {
        key: min_max([f[key] for f in raw.values()])
        for key in WEIGHTS
    }

    scores = {}
    for pid, feats in raw.items():
        scaled = {k: scale(v, *bounds[k]) for k, v in feats.items()}
        scores[pid] = round(weighted_score(scaled, WEIGHTS) * 10, 2)
    return scores