"""Quick test: print the top 10 players by Form score."""

from sqlalchemy import select

from app.advisors.form import get_form_scores
from app.database import SessionLocal
from app.models import Player

db = SessionLocal()
try:
    scores = get_form_scores(db)
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]
    players = {p.id: p for p in db.scalars(select(Player)).all()}

    for pid, score in top:
        p = players[pid]
        print(f"{score:5.2f}  {p.web_name:20s}  form={p.form}  pts={p.total_points}")
finally:
    db.close()