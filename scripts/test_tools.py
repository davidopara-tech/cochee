"""Test the LLM-facing tools with realistic user questions."""

from app.database import SessionLocal
from app.tools import find_similar_players, get_top_players


def _print(title: str, players: list[dict]) -> None:
    print(f"\n=== {title} ===")
    for p in players:
        if "total" in p:
            print(
                f"  {p['total']:5.2f}  {p['name']:18s} {p['position']:3s} "
                f"£{p['price']:4.1f}m  form={p['form']:5.2f}  "
                f"fix={p['fixtures']:5.2f}  val={p['value']:5.2f}  ({p['reason']})"
            )
        else:
            print(
                f"       {p['name']:18s} {p['position']:3s} "
                f"£{p['price']:4.1f}m  form={p['form']:5.2f}  pts={p['points']}"
            )

db = SessionLocal()
try:
    _print(
        "Scenario 1: 'I've got £8.5m. I need a midfielder.'",
        get_top_players(db, position=3, max_price=85, min_minutes=200, limit=5),
    )

    _print(
        "Scenario 2: 'Best defender under £5m'",
        get_top_players(db, position=2, max_price=50, min_minutes=200, limit=5),
    )

    _print(
        "Scenario 3: 'Cheaper alternatives to Saka'",
        find_similar_players(db, "Saka", same_position=True, max_price=75, limit=5),
    )

    _print(
        "Scenario 4: 'I care most about form'",
        get_top_players(db, position=3, weights={"form": 0.7, "fixtures": 0.15, "value": 0.15}, limit=5),
    )
finally:
    db.close()