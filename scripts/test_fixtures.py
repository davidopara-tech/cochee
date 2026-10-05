"""Quick test: print the top 10 players by Fixtures score."""

from sqlalchemy import select

from app.advisors.fixtures import get_fixture_scores
from app.database import SessionLocal
from app.models import Player

db = SessionLocal()
try:
    scores = get_fixture_scores(db)
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    players = {p.id: p for p in db.scalars(select(Player)).all()}

    for pid, score in top:
        p = players[pid]
        print(f"{score:5.2f}  {p.web_name:20s}  team_id={p.team_id}")
finally:
    db.close()