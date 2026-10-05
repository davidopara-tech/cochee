"""Tools the LLM can call. Each returns small, clean dicts (not ORM objects)."""

from sqlalchemy import select

from app.advisors.combined import get_combined_scores
from app.models import Player, Team

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _team_lookup(db) -> dict[int, str]:
    """Returns {team_id: short_name} for translating to human-readable names."""
    return {t.id: t.short_name for t in db.scalars(select(Team)).all()}


def _reason(components: dict) -> str:
    """One-line plain-English summary of a player's strongest and weakest metric."""
    best = max(components, key=components.get)
    worst = min(components, key=components.get)
    if components[best] - components[worst] < 1.5:
        return "well-rounded across form, fixtures, and value"
    return f"strong on {best}, weak on {worst}"


def get_top_players(
    db,
    position: int | None = None,
    max_price: int | None = None,
    min_minutes: int = 0,
    only_available: bool = True,
    limit: int = 5,
    weights: dict[str, float] | None = None,
) -> list[dict]:
    """
    Rank players by combined advisor score, filtered by the user's constraints.

    position: 1=GK, 2=DEF, 3=MID, 4=FWD. None = all positions.
    max_price: in tenths of a million (85 = £8.5m). None = no cap.
    min_minutes: exclude players below this season minutes total.
    only_available: if True, exclude injured/suspended players.
    limit: how many results to return.
    weights: optional {"form": 0.5, "fixtures": 0.3, "value": 0.2} to override defaults.
    """
    scores = get_combined_scores(db, weights=weights)
    teams = _team_lookup(db)

    players = db.scalars(select(Player)).all()

    filtered = [
        p for p in players
        if (position is None or p.element_type == position)
        and (max_price is None or p.now_cost <= max_price)
        and p.minutes >= min_minutes
        and (not only_available or p.status == "a")
    ]

    ranked = sorted(filtered, key=lambda p: scores[p.id]["total"], reverse=True)[:limit]

    return [
        {
            "id": p.id,
            "name": p.web_name,
            "team": teams.get(p.team_id, "?"),
            "position": POSITIONS.get(p.element_type, "?"),
            "price": round(p.now_cost / 10, 1),
            "total": scores[p.id]["total"],
            "form": scores[p.id]["form"],
            "fixtures": scores[p.id]["fixtures"],
            "value": scores[p.id]["value"],
            "reason": _reason({
                "form": scores[p.id]["form"],
                "fixtures": scores[p.id]["fixtures"],
                "value": scores[p.id]["value"],
            }),
        }
        for p in ranked
    ]

def find_similar_players(
    db,
    player_name: str,
    same_position: bool = True,
    max_price: int | None = None,
    limit: int = 5,
) -> list[dict]:
    """
    Find players statistically similar to the named player.
    Uses pgvector distance on the embedding column.

    same_position: restrict matches to the target player's FPL position.
    max_price: optional upper price bound in tenths (85 = £8.5m).
    """
    target = db.scalars(
        select(Player).where(Player.web_name.ilike(f"%{player_name}%"))
    ).first()
    if target is None:
        return []

    stmt = (
        select(Player)
        .where(Player.id != target.id)
        .where(Player.status == "a")
        .order_by(Player.embedding.l2_distance(target.embedding))
        .limit(limit)
    )
    if same_position:
        stmt = stmt.where(Player.element_type == target.element_type)
    if max_price is not None:
        stmt = stmt.where(Player.now_cost <= max_price)

    teams = _team_lookup(db)
    matches = db.scalars(stmt).all()

    return [
        {
            "id": p.id,
            "name": p.web_name,
            "team": teams.get(p.team_id, "?"),
            "position": POSITIONS.get(p.element_type, "?"),
            "price": round(p.now_cost / 10, 1),
            "form": round(p.form, 2),
            "points": p.total_points,
        }
        for p in matches
    ]