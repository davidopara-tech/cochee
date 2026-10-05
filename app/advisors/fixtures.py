"""Fixtures advisor: scores how easy each player's upcoming matches are."""

from sqlalchemy import select

from app.advisors.common import min_max, scale, weighted_score
from app.models import Fixture, Player

WEIGHTS = {
    "difficulty": 0.70,
    "count": 0.30,
}

INVERTED = {"difficulty"}  # lower is better for these features
NEXT_N = 3


def _team_fixture_stats(db) -> dict[int, dict[str, float]]:
    """For each team: {'difficulty': avg of next 3, 'count': how many remain}."""
    fixtures = db.scalars(
        select(Fixture)
        .where(Fixture.finished.is_(False))
        .where(Fixture.gameweek_id.isnot(None))
        .order_by(Fixture.gameweek_id, Fixture.kickoff_time)
    ).all()

    per_team: dict[int, list[int]] = {}
    for f in fixtures:
        per_team.setdefault(f.home_team_id, []).append(f.team_h_difficulty)
        per_team.setdefault(f.away_team_id, []).append(f.team_a_difficulty)

    return {
        team_id: {
            "difficulty": sum(diffs[:NEXT_N]) / len(diffs[:NEXT_N]),
            "count": float(len(diffs[:NEXT_N])),
        }
        for team_id, diffs in per_team.items()
    }


def get_fixture_scores(db) -> dict[int, float]:
    """Returns {player_id: fixture_score} where score is 0-10."""
    team_stats = _team_fixture_stats(db)
    players = db.scalars(select(Player)).all()

    default = {"difficulty": 3.0, "count": 0.0}
    raw = {p.id: team_stats.get(p.team_id, default) for p in players}

    bounds = {k: min_max([f[k] for f in raw.values()]) for k in WEIGHTS}

    scores = {}
    for pid, feats in raw.items():
        scaled = {
            k: (1.0 - scale(v, *bounds[k])) if k in INVERTED else scale(v, *bounds[k])
            for k, v in feats.items()
        }
        scores[pid] = round(weighted_score(scaled, WEIGHTS) * 10, 2)
    return scores