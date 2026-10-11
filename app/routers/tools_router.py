from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database  import get_db
from app.schemas import SimilarPlayersRequest, TopPlayersRequest, ComparePlayerRequest
from app.tools import compare_players as compare_players_tool
from  app.tools import find_similar_players, get_top_players

router = APIRouter(prefix = "/tools",
                   tags = ["Tools"])


@router.post("/top-players", operation_id="top_players")
def top_players(request: TopPlayersRequest, db: Session = Depends(get_db)) -> dict:
    """
    Rank players by combined score, filtered by user constraints.

    Use this when the user asks for 'best', 'top', 'cheapest', or
    'who should I captain' — questions with no specific player named.

    Filters: position (1=GK 2=DEF 3=MID 4=FWD), team short code or full name,
    max_price (in tenths: 85 = £8.5m), min/max ownership (0-100 percent).

    Returns {"players": [{name, team, position, price, total, form,
    fixtures, value, reason}, ...]} ranked best-first.
    """
    ...
    return { "players" : get_top_players(
        db,
        position = request.position,
        max_price = request.max_price,
        limit = request.limit,
        weights = request.weights,
        team= request.team,
        min_ownership = request.min_ownership,
        max_ownership = request.max_ownership
)
    }


@router.post("/similar-players", operation_id="similar_players")
def similar_players(request: SimilarPlayersRequest, db: Session = Depends(get_db)) -> dict:
    """
    Find players statistically similar to a named player.

    Use this when the user names one specific player and asks for
    'players like X', 'similar to X', or 'replacements for X'.

    Returns one of three statuses:
      - "ok": unique player found, similar players returned
      - "ambiguous": name matches multiple players, returns candidates
        for the user to choose from (ask them which one they meant)
      - "not_found": no player matches the name
    """
    ...
    result = find_similar_players(
        db,
        player_name=request.player_name,
        same_position=request.same_position,
        max_price=request.max_price,
        limit=request.limit,
    )
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="No matching player found.")
    return result

@router.post("/compare-players", operation_id="compare_players")
def compare_players(request: ComparePlayerRequest, db: Session = Depends(get_db)) -> dict:
    """
    Compare 2-5 players side by side on identical metrics.

    Use this when the user says 'compare A and B', 'A vs B',
    or asks which of several named players is better.

    Returns {status, players: [...], missing: [...], ambiguous: [...]}.
    Status is "ok" (all found), "partial" (some missing or ambiguous),
    or "not_found". Each player dict has: name, team, position, price,
    total, form, fixtures, value, points, minutes, ownership.
    """
    ...
    return compare_players_tool(db, request.names)