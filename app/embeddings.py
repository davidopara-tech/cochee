"""Computes the 24-feature embedding vector for every player."""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Player, Team


def _setpiece_score(player: Player) -> float:
    """Turns set-piece duties into a 0-1 score. First choice = 1.0."""
    def order_score(order):
        if order is None:
            return 0.0
        return {1: 1.0, 2: 0.5, 3: 0.25}.get(order, 0.1)

    return (
        order_score(player.penalties_order)
        + order_score(player.direct_freekicks_order)
        + order_score(player.corners_and_indirect_freekicks_order)
    ) / 3.0


def _availability(player: Player) -> float:
    """0-1 chance of playing. FPL sends null when the player is fully fit."""
    if player.chance_of_playing_this_round is None:
        return 1.0
    return player.chance_of_playing_this_round / 100.0


def _fixture_difficulty(player: Player, team_difficulty: dict[int, float]) -> float:
    """Average difficulty of the player's team's next 3 fixtures."""
    return team_difficulty.get(player.team_id, 3.0)


def _feature_specs():
    """The 24 features. Order matters - it becomes the vector position."""
    return [
        ("position",          lambda p, ctx: p.element_type,                          False),
        ("price",             lambda p, ctx: p.now_cost,                              False),
        ("form",              lambda p, ctx: p.form,                                  False),
        ("ppg",               lambda p, ctx: p.points_per_game,                       False),
        ("total_points",      lambda p, ctx: p.total_points,                          False),
        ("goals",             lambda p, ctx: p.goals_scored,                          False),
        ("assists",           lambda p, ctx: p.assists,                               False),
        ("xg90",              lambda p, ctx: p.expected_goals_per_90,                 False),
        ("xa90",              lambda p, ctx: p.expected_assists_per_90,               False),
        ("xgi90",             lambda p, ctx: p.expected_goal_involvements_per_90,     False),
        ("ict",               lambda p, ctx: p.ict_index,                             False),
        ("influence",         lambda p, ctx: p.influence,                             False),
        ("creativity",        lambda p, ctx: p.creativity,                            False),
        ("threat",            lambda p, ctx: p.threat,                                False),
        ("value_form",        lambda p, ctx: p.form / max(p.now_cost, 1),             False),
        ("value_season",      lambda p, ctx: p.total_points / max(p.now_cost, 1),     False),
        ("ownership",         lambda p, ctx: p.selected_by_percent,                   False),
        ("minutes",           lambda p, ctx: p.minutes,                               False),
        ("fixture_difficulty",lambda p, ctx: ctx["fixture_difficulty"][p.team_id],    False),
        ("clean_sheets",      lambda p, ctx: p.clean_sheets,                          False),
        ("yellow_cards",      lambda p, ctx: p.yellow_cards,                          True),
        ("red_cards",         lambda p, ctx: p.red_cards,                             True),
        ("setpiece",          lambda p, ctx: ctx["setpiece"][p.id],                   False),
        ("availability",      lambda p, ctx: ctx["availability"][p.id],               False),
    ]


def _min_max(values: list[float]) -> tuple[float, float]:
    """Returns (min, max). Handles the case where every value is identical."""
    lo, hi = min(values), max(values)
    if hi == lo:
        return lo, lo + 1.0  # avoids division by zero
    return lo, hi


def _scale(value: float, lo: float, hi: float, invert: bool) -> float:
    scaled = (value - lo) / (hi - lo)
    scaled = max(0.0, min(1.0, scaled))  # clamp to [0, 1]
    return 1.0 - scaled if invert else scaled


def build_embeddings() -> None:
    """Computes and writes the embedding vector for every player."""
    db = SessionLocal()
    try:
        players = db.scalars(select(Player)).all()
        print(f"Computing embeddings for {len(players)} players...")

        # Pre-compute context that doesn't fit the simple getter pattern.
        ctx = {
            "setpiece": {p.id: _setpiece_score(p) for p in players},
            "availability": {p.id: _availability(p) for p in players},
            "fixture_difficulty": _team_fixture_difficulty(db),
        }

        specs = _feature_specs()

        # Pass 1: find min/max for each feature across all players.
        bounds = []
        for name, getter, invert in specs:
            values = [float(getter(p, ctx)) for p in players]
            bounds.append(_min_max(values))

        # Pass 2: scale each player's 24 features into a vector.
        for player in players:
            vector = [
                _scale(float(getter(player, ctx)), lo, hi, invert)
                for (name, getter, invert), (lo, hi) in zip(specs, bounds)
            ]
            player.embedding = vector

        db.commit()
        print("Done.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _team_fixture_difficulty(db) -> dict[int, float]:
    """
    Average difficulty of each team's next 3 unplayed fixtures.
    Used as the fixture_difficulty feature.
    """
    from app.models import Fixture

    fixtures = db.scalars(
        select(Fixture).where(Fixture.finished.is_(False)).order_by(Fixture.kickoff_time)
    ).all()

    per_team: dict[int, list[int]] = {}
    for f in fixtures:
        if f.gameweek_id is None:
            continue
        per_team.setdefault(f.home_team_id, []).append(f.team_h_difficulty)
        per_team.setdefault(f.away_team_id, []).append(f.team_a_difficulty)

    return {
        team_id: (sum(diffs[:3]) / len(diffs[:3])) if diffs else 3.0
        for team_id, diffs in per_team.items()
    }