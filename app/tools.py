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


def _team_id_by_name(db, code: str) -> int | None:
    """Find team_id by short_name ('ARS') or full name ('Arsenal'). Case-insensitive."""
    code = code.lower()
    for team in db.scalars(select(Team)).all():
        if team.short_name.lower() == code or team.name.lower() == code:
            return team.id
    return None


def get_top_players(
    db,
    position: int | None = None,
    team: str | None = None,
    max_price: int | None = None,
    min_ownership: float | None = None,
    max_ownership: float | None = None,
    min_minutes: int = 0,
    only_available: bool = True,
    limit: int = 5,
    weights: dict[str, float] | None = None,
) -> list[dict]:
    """
    Rank players by combined advisor score, filtered by the user's constraints.

    position: 1=GK, 2=DEF, 3=MID, 4=FWD. None = all positions.
    team: club short code ('ARS') or full name ('Arsenal'). None = all teams.
    max_price: in tenths of a million (85 = £8.5m). None = no cap.
    min_ownership / max_ownership: percent of managers owning (0-100).
    min_minutes: exclude players below this season minutes total.
    only_available: if True, exclude injured/suspended players.
    limit: how many results to return.
    weights: optional {"form": 0.5, "fixtures": 0.3, "value": 0.2} to override defaults.
    """
    scores = get_combined_scores(db, weights=weights)
    teams = _team_lookup(db)

    if team is not None:
        team_id = _team_id_by_name(db, team)
        if team_id is None:
            return []
    else:
        team_id = None

    players = db.scalars(select(Player)).all()

    filtered = [
        p for p in players
        if (position is None or p.element_type == position)
        and (team_id is None or p.team_id == team_id)
        and (min_ownership is None or p.selected_by_percent >= min_ownership)
        and (max_ownership is None or p.selected_by_percent <= max_ownership)
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
) -> dict:
    """
    Find players statistically similar to the named player.
    Returns a dict with a 'status' discriminator:
      - {"status": "ok", "players": [...]}
      - {"status": "ambiguous", "candidates": [...]}
      - {"status": "not_found"}
    """
    tokens = player_name.lower().split()
    if len(tokens) == 0:
        return {"status": "not_found"}
    conditions = [Player.search_name.op("~*")(f"\\y{token}\\y") for token in tokens]

    matches = db.scalars(
        select(Player).where(*conditions)
    ).all()

    if len(matches) == 0:
        return {"status": "not_found"}

    if len(matches) > 1:
        teams = _team_lookup(db)
        return {
            "status": "ambiguous",
            "candidates": [
            {"id": p.id, "name": p.web_name, "team": teams.get(p.team_id, "?"), "position": POSITIONS.get(p.element_type, "?")}
            for p in matches[:5]
            ],
        }

    target = matches[0]

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
    results = db.scalars(stmt).all()

    return {
        "status": "ok",
        "players": [
            {
                "id": p.id,
                "name": p.web_name,
                "team": teams.get(p.team_id, "?"),
                "position": POSITIONS.get(p.element_type, "?"),
                "price": round(p.now_cost / 10, 1),
                "form": round(p.form, 2),
                "points": p.total_points,
            }
            for p in results
        ],
    }
def _find_one_player(db, name: str) -> dict:
    """Find a player by name. Returns:
       {"status": "ok", "player": <Player>}
       {"status": "not_found"}
       {"status": "ambiguous", "candidates": [{id, name, team}, ...]}
    """
    tokens = name.lower().split()
    if len(tokens) == 0:
        return {"status": "not_found"}
    conditions = [Player.search_name.op("~*")(f"\\y{token}\\y") for token in tokens]
    matches = db.scalars(select(Player).where(*conditions)).all()

    if len(matches) == 0:
        return {"status": "not_found"}
    if len(matches) == 1:
        return {"status": "ok", "player": matches[0]}

    teams = _team_lookup(db)
    return {
        "status": "ambiguous",
        "candidates": [
            {"id": p.id, "name": p.web_name, "team": teams.get(p.team_id, "?"),  "position": POSITIONS.get(p.element_type, "?"),}
            for p in matches[:5]
       ],
    }


def compare_players(db, names: list[str]) -> dict:
    """
    Compare 2-5 players side by side.

    INPUT:
        names = ["Palmer", "Salah", "Xyzzy"]

    INTERMEDIATE DATA (built once, reused):

        scores = {
            12:  {"total": 6.9,  "form": 5.1,  "fixtures": 4.2,  "value": 7.8},
            154: {"total": 8.1,  "form": 9.2,  "fixtures": 6.4,  "value": 7.8},
            283: {"total": 7.8,  "form": 7.5,  "fixtures": 5.9,  "value": 8.4},
            ...
        }   # keyed by player.id

        teams = {
            1:  "ARS",
            11: "LIV",
            14: "MCI",
            ...
        }   # keyed by team_id

    LOOP TRACE:
        name = "Palmer"   → _find_one_player → {"status": "ok", ...} → found.append({...})
        name = "Salah"    → _find_one_player → {"status": "ok", ...} → found.append({...})
        name = "Xyzzy"    → _find_one_player → {"status": "not_found"} → missing.append("Xyzzy")

    OUTPUT — one of three shapes:

        # All matched
        {
            "status": "ok",
            "players": [
                {"name": "Palmer", "team": "CHE", "position": "MID", "price": 10.5,
                 "total": 8.1, "form": 9.2, "fixtures": 6.4, "value": 7.8,
                 "points": 142, "minutes": 1800, "ownership": 25.4},
                {"name": "Salah",  "team": "LIV", "position": "MID", "price": 13.1,
                 "total": 7.8, "form": 7.5, "fixtures": 5.9, "value": 8.4,
                 "points": 155, "minutes": 1900, "ownership": 45.2},
            ],
        }

        # Some matched, some didn't
        {
            "status": "partial",
            "players": [ {...Palmer...}, {...Salah...} ],
            "missing": ["Xyzzy"],
            "ambiguous": [
                {"query": "Smith", "candidates": [{"id": 1, "name": "Smith", "team": "ARS"}]}
            ],
        }

        # None matched
        {
            "status": "not_found",
            "missing": ["Xyzzy"],
        }
    """
    names = list(dict.fromkeys(names))
    if len(names) < 2:
        return {"status": "not_found", "missing": names}
    
    #scores holds all the combined scores for 
    # all players, so we can look up each player by ID
    scores = get_combined_scores(db)
    teams = _team_lookup(db)

    found = []
    missing = []
    ambiguous = []
    for name in names:
        result = _find_one_player(db, name)

        if result["status"] == "not_found":
            missing.append(name)
            continue

        if result["status"] == "ambiguous":
            ambiguous.append({"query": name, "candidates": result["candidates"]})
            continue

        player = result["player"]
        s = scores[player.id] #
        found.append({
            "name": player.web_name,
            "team": teams.get(player.team_id, "?"),
            "position": POSITIONS.get(player.element_type, "?"),
            "price": round(player.now_cost / 10, 1),
            "total": s["total"],
            "form": s["form"],
            "fixtures": s["fixtures"],
            "value": s["value"],
            "points": player.total_points,
            "minutes": player.minutes,
            "ownership": round(player.selected_by_percent, 1),
        })

    if len(found) == 0 and len(ambiguous) == 0:
        return {"status": "not_found", "missing": missing}

    if len(missing) > 0 or len(ambiguous) > 0:
        response = {"status": "partial", "players": found, "missing": missing}
        if len(ambiguous) > 0:
            response["ambiguous"] = ambiguous
        return response

    return {"status": "ok", "players": found}