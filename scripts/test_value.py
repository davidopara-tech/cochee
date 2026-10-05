"""Quick test: print the top 10 players by Value score."""

from sqlalchemy import select

from app.advisors.value import get_value_scores
from app.database import SessionLocal
from app.models import Player

db = SessionLocal()
try:
    scores = get_value_scores(db)
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    players = {p.id: p for p in db.scalars(select(Player)).all()}

    for pid, score in top:
        p = players[pid]
        print(
            f"{score:5.2f}  {p.web_name:20s}  "
            f"£{p.now_cost/10:.1f}m  pts={p.total_points}  own={p.selected_by_percent}%"
        )
finally:
    db.close()