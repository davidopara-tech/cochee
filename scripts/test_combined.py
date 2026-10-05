"""Quick test: top 10 players by combined score, with component breakdown."""

from sqlalchemy import select

from app.advisors.combined import get_combined_scores
from app.database import SessionLocal
from app.models import Player

db = SessionLocal()
try:
    scores = get_combined_scores(db)
    top = sorted(scores.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
    players = {p.id: p for p in db.scalars(select(Player)).all()}

    for pid, s in top:
        p = players[pid]
        print(
            f"{s['total']:5.2f}  {p.web_name:18s}  "
            f"form={s['form']:5.2f}  fix={s['fixtures']:5.2f}  val={s['value']:5.2f}"
        )
finally:
    db.close()