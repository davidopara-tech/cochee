"""Transforms FPL API data and writes it to the database."""

from datetime import datetime

from sqlalchemy.dialects.postgresql import insert

from app.database import SessionLocal
from app.fpl_client import fetch_bootstrap, fetch_fixtures
from app.models import Fixture, Gameweek, Player, Team


def _upsert(db, model, rows: list[dict]) -> int:
    """Insert rows, or update existing ones by primary key. Returns row count."""
    if not rows:
        return 0

    stmt = insert(model).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={col: stmt.excluded[col] for col in rows[0].keys() if col != "id"},
    )
    db.execute(stmt)
    return len(rows)


def _to_float(value) -> float:
    """FPL sends many numbers as strings; null or bad values become 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _parse_dt(value: str | None) -> datetime | None:
    """Parse FPL's ISO timestamp, e.g. '2026-08-15T11:30:00Z'."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ingest_teams(db, bootstrap: dict) -> int:
    rows = [
        {
            "id": t["id"],
            "name": t["name"],
            "short_name": t["short_name"],
            "strength": t.get("strength") or 0,
            "strength_overall_home": t.get("strength_overall_home") or 0,
            "strength_overall_away": t.get("strength_overall_away") or 0,
            "strength_attack_home": t.get("strength_attack_home") or 0,
            "strength_attack_away": t.get("strength_attack_away") or 0,
            "strength_defence_home": t.get("strength_defence_home") or 0,
            "strength_defence_away": t.get("strength_defence_away") or 0,
        }
        for t in bootstrap["teams"]
    ]
    return _upsert(db, Team, rows)


def _ingest_gameweeks(db, bootstrap: dict) -> int:
    rows = [
        {
            "id": e["id"],
            "name": e["name"],
            "deadline_time": _parse_dt(e["deadline_time"]),
            "is_current": e["is_current"],
            "is_next": e["is_next"],
            "finished": e["finished"],
            "data_checked": e["data_checked"],
        }
        for e in bootstrap["events"]
    ]
    return _upsert(db, Gameweek, rows)


def _ingest_players(db, bootstrap: dict) -> int:
    rows = [
        {
            "id": p["id"],
            "team_id": p["team"],
            "first_name": p["first_name"],
            "second_name": p["second_name"],
            "web_name": p["web_name"],
            "element_type": p["element_type"],
            "status": p["status"],
            "news": p.get("news") or None,
            "chance_of_playing_this_round": p.get("chance_of_playing_this_round"),
            "chance_of_playing_next_round": p.get("chance_of_playing_next_round"),
            "now_cost": p["now_cost"],
            "cost_change_start": p.get("cost_change_start", 0),
            "cost_change_event": p.get("cost_change_event", 0),
            "selected_by_percent": _to_float(p.get("selected_by_percent")),
            "total_points": p.get("total_points", 0),
            "points_per_game": _to_float(p.get("points_per_game")),
            "minutes": p.get("minutes", 0),
            "goals_scored": p.get("goals_scored", 0),
            "assists": p.get("assists", 0),
            "clean_sheets": p.get("clean_sheets", 0),
            "goals_conceded": p.get("goals_conceded", 0),
            "bonus": p.get("bonus", 0),
            "bps": p.get("bps", 0),
            "yellow_cards": p.get("yellow_cards", 0),
            "red_cards": p.get("red_cards", 0),
            "saves": p.get("saves", 0),
            "form": _to_float(p.get("form")),
            "form_weighted": _to_float(p.get("form_weighted")),
            "event_points": p.get("event_points"),
            "expected_goals_per_90": _to_float(p.get("expected_goals_per_90")),
            "expected_assists_per_90": _to_float(p.get("expected_assists_per_90")),
            "expected_goal_involvements_per_90": _to_float(
                p.get("expected_goal_involvements_per_90")
            ),
            "expected_goals_conceded_per_90": _to_float(
                p.get("expected_goals_conceded_per_90")
            ),
            "ict_index": _to_float(p.get("ict_index")),
            "influence": _to_float(p.get("influence")),
            "creativity": _to_float(p.get("creativity")),
            "threat": _to_float(p.get("threat")),
            "penalties_order": p.get("penalties_order"),
            "direct_freekicks_order": p.get("direct_freekicks_order"),
            "corners_and_indirect_freekicks_order": p.get(
                "corners_and_indirect_freekicks_order"
            ),
        }
        for p in bootstrap["elements"]
    ]
    return _upsert(db, Player, rows)


def _ingest_fixtures(db, fixtures_json: list) -> int:
    rows = [
        {
            "id": f["id"],
            "gameweek_id": f["event"],
            "home_team_id": f["team_h"],
            "away_team_id": f["team_a"],
            "kickoff_time": _parse_dt(f.get("kickoff_time")),
            "team_h_difficulty": f["team_h_difficulty"],
            "team_a_difficulty": f["team_a_difficulty"],
            "team_h_score": f.get("team_h_score"),
            "team_a_score": f.get("team_a_score"),
            "finished": f["finished"],
            "started": f.get("started"),
            "finished_provisional": f.get("finished_provisional", False),
        }
        for f in fixtures_json
    ]
    return _upsert(db, Fixture, rows)


def sync_all() -> None:
    """Fetch everything from FPL and upsert it into the four tables."""
    print("Fetching from FPL...")
    bootstrap = fetch_bootstrap()
    fixtures = fetch_fixtures()

    db = SessionLocal()
    try:
        counts = {
            "teams": _ingest_teams(db, bootstrap),
            "gameweeks": _ingest_gameweeks(db, bootstrap),
            "players": _ingest_players(db, bootstrap),
            "fixtures": _ingest_fixtures(db, fixtures),
        }
        db.commit()
        for name, count in counts.items():
            print(f"  {name}: {count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()