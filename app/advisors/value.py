"""Value advisor: scores points-per-pound and rewards differentials."""

from sqlalchemy import select

from app.advisors.common import min_max, scale, weighted_score
from app.models import Player

WEIGHTS = {
    "value_season": 0.50,
    "value_form": 0.30,
    "ownership": 0.20,
}

INVERTED = {"ownership"}
MIN_COST = 40  # £4.0m — the cheapest possible FPL price


def _raw_features(player: Player) -> dict[str, float]:
    """Points-per-million and ownership for one player."""
    price = max(player.now_cost, MIN_COST)
    return {
        "value_season": player.total_points / price,
        "value_form": player.form / price,
        "ownership": player.selected_by_percent,
    }


def get_value_scores(db) -> dict[int, float]:
    """Returns {player_id: value_score} where score is 0-10."""
    players = db.scalars(select(Player)).all()
    raw = {p.id: _raw_features(p) for p in players}

    bounds = {k: min_max([f[k] for f in raw.values()]) for k in WEIGHTS}

    scores = {}
    for pid, feats in raw.items():
        scaled = {
            k: (1.0 - scale(v, *bounds[k])) if k in INVERTED else scale(v, *bounds[k])
            for k, v in feats.items()
        }
        scores[pid] = round(weighted_score(scaled, WEIGHTS) * 10, 2)
    return scores