"""Tools the LLM can call. Each returns small, clean dicts (not ORM objects)."""

from sqlalchemy import or_, select

from app.advisors.combined import get_combined_scores
from app.models import Fixture, Player, Team

POSITIONS = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def _team_lookup(db) -> dict[int, str]:
    """Returns {team_id: short_name} for translating to human-readable names."""
    return {t.id: t.short_name for t in db.scalars(select(Team)).all()}

def _team_full_names(db) -> dict[int, str]:
    """Returns {team_id: full_name} for human-readable output."""
    return {t.id: t.name for t in db.scalars(select(Team)).all()}


def _full_name(p: Player) -> str:
    """Best human-readable name for a player. Falls back to web_name."""
    if p.first_name and p.second_name:
        return f"{p.first_name} {p.second_name}"
    return p.web_name


def _difficulty_label(rating: int) -> str:
    """Plain-English label for FPL's 1-5 difficulty rating."""
    if rating <= 2:
        return "easy"
    if rating == 3:
        return "medium"
    return "hard"


def _phrase_form(score: float) -> str:
    if score >= 8.0: return "in red-hot form"
    if score >= 6.0: return "in strong form"
    if score >= 4.0: return "in decent form"
    if score >= 2.0: return "in patchy form"
    return "out of form"


def _phrase_fixtures(score: float) -> str:
    if score >= 8.0: return "a very kind run of fixtures"
    if score >= 6.0: return "a favourable run of fixtures"
    if score >= 4.0: return "mixed fixtures"
    if score >= 2.0: return "a tough run of fixtures"
    return "a brutal run of fixtures"


def _phrase_value(score: float) -> str:
    if score >= 8.0: return "outstanding value"
    if score >= 6.0: return "good value"
    if score >= 4.0: return "fair value"
    if score >= 2.0: return "poor value"
    return "very expensive"


def _reason(components: dict) -> str:
    """Football-language summary of a player's form, fixtures, and value."""
    form = _phrase_form(components["form"])
    fixtures = _phrase_fixtures(components["fixtures"])
    value = _phrase_value(components["value"])
    return f"{form.capitalize()}, {fixtures}, {value}."


def _team_id_by_name(db, code: str) -> int | None:
    """Find team_id by short_name ('ARS') or full name ('Arsenal'). Case-insensitive."""
    code = code.lower()
    for team in db.scalars(select(Team)).all():
        if team.short_name.lower() == code or team.name.lower() == code:
            return team.id
    return None


def _find_one_player(db, name: str) -> dict:
    """
    Find a player by name. Two-tier search:
      1. Word-boundary match (strict): each token must appear as a whole word.
      2. Substring fallback (loose): only fires if step 1 found nothing.

    Returns one of:
      {"status": "ok", "player": <Player>}
      {"status": "not_found"}
      {"status": "ambiguous", "candidates": [{id, name, team, position}, ...]}
    """
    tokens = name.lower().split()
    if len(tokens) == 0:
        return {"status": "not_found"}

    # Step 1: strict word-boundary match
    conditions = [Player.search_name.op("~*")(f"\\y{token}\\y") for token in tokens]
    matches = db.scalars(select(Player).where(*conditions)).all()

    # Step 2: substring fallback if strict found nothing
    if len(matches) == 0:
        conditions = [Player.search_name.ilike(f"%{token}%") for token in tokens]
        matches = db.scalars(select(Player).where(*conditions)).all()

    if len(matches) == 0:
        return {"status": "not_found"}
    if len(matches) == 1:
        return {"status": "ok", "player": matches[0]}

    teams = _team_lookup(db)
    return {
        "status": "ambiguous",
        "candidates": [
            {
                "id": p.id,
                "name": _full_name(p),
                "team": teams.get(p.team_id, "?"),
                "position": POSITIONS.get(p.element_type, "?"),
            }
            for p in matches[:5]
        ],
    }

def get_top_players(
    db,
    position: int | None = None,
    team: str | None = None,
    max_price: int | None = None,
    min_price: int | None = None,
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
        and (min_price is None or p.now_cost >= min_price)
        and p.minutes >= min_minutes
        and (not only_available or p.status == "a")
    ]

    ranked = sorted(filtered, key=lambda p: scores[p.id]["total"], reverse=True)[:limit]

    return [
        {
            "id": p.id,
            "name": _full_name(p),
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

    Returns one of:
      {"status": "ok", "players": [...]}
      {"status": "ambiguous", "candidates": [...]}
      {"status": "not_found"}
    """
    lookup = _find_one_player(db, player_name)

    if lookup["status"] == "not_found":
        return {"status": "not_found"}
    if lookup["status"] == "ambiguous":
        return {"status": "ambiguous", "candidates": lookup["candidates"]}

    target = lookup["player"]

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


def compare_players(db, names: list[str]) -> dict:
    """
    Compare 2-5 players side by side.

    Returns one of:
      {"status": "ok", "players": [...]}
      {"status": "partial", "players": [...], "missing": [...], "ambiguous": [...]}
      {"status": "not_found", "missing": [...]}
    """
    names = list(dict.fromkeys(names))
    if len(names) < 2:
        return {"status": "not_found", "missing": names}

    scores = get_combined_scores(db)
    teams = _team_lookup(db)

    found = []
    missing = []
    ambiguous = []

    for name in names:
        lookup = _find_one_player(db, name)

        if lookup["status"] == "not_found":
            missing.append(name)
            continue

        if lookup["status"] == "ambiguous":
            ambiguous.append({"query": name, "candidates": lookup["candidates"]})
            continue

        player = lookup["player"]
        s = scores[player.id]
        found.append({
            "name": _full_name(player),
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

def get_player_fixtures(db, player_name: str, num_gameweeks: int = 5) -> dict:
    """
    Return a player's upcoming fixtures with opponent, venue, and difficulty.

    difficulty is FPL's own rating: 1 = easiest, 5 = hardest.
    difficulty_label translates that to 'easy' / 'medium' / 'hard'.

    Returns one of:
      {"status": "ok", "player": ..., "team": ..., "fixtures": [...]}
      {"status": "ambiguous", "candidates": [...]}
      {"status": "not_found"}
    """
    lookup = _find_one_player(db, player_name)
    if lookup["status"] != "ok":
        return lookup

    player = lookup["player"]
    short = _team_lookup(db)
    full = _team_full_names(db)

    rows = db.scalars(
        select(Fixture)
        .where(
            or_(
                Fixture.home_team_id == player.team_id,
                Fixture.away_team_id == player.team_id,
            ),
            Fixture.finished.is_(False),
            Fixture.gameweek_id.is_not(None),
        )
        .order_by(Fixture.gameweek_id)
        .limit(num_gameweeks)
    ).all()

    fixtures = []
    for f in rows:
        is_home = f.home_team_id == player.team_id
        opponent_id = f.away_team_id if is_home else f.home_team_id
        difficulty = f.team_h_difficulty if is_home else f.team_a_difficulty
        fixtures.append({
            "gameweek": f.gameweek_id,
            "opponent": full.get(opponent_id, short.get(opponent_id, "?")),
            "venue": "home" if is_home else "away",
            "difficulty": difficulty,
            "difficulty_label": _difficulty_label(difficulty),
        })

    return {
        "status": "ok",
        "player": _full_name(player),
        "team": full.get(player.team_id, short.get(player.team_id, "?")),
        "fixtures": fixtures,
    }