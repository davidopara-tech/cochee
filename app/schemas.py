from pydantic import BaseModel, Field


class TopPlayersRequest(BaseModel):
    position: int | None = Field(
        default=None, ge=1, le=4,
        description="1=GK, 2=DEF, 3=MID, 4=FWD. Omit for all positions."
    )
    team: str | None = Field(
        default=None, min_length=2, max_length=4,
        description="Club short code ('ARS') or full name ('Arsenal'). Omit for all teams."
    )
    max_price: int | None = Field(
        default=None, gt=0,
        description="Maximum price in tenths of a million (85 = £8.5m). Omit for no cap."
    )
    min_ownership: float | None = Field(
        default=None, ge=0, le=100,
        description="Minimum ownership percent (0-100). Omit for no minimum."
    )
    max_ownership: float | None = Field(
        default=None, ge=0, le=100,
        description="Maximum ownership percent (0-100). Omit for no maximum."
    )
    limit: int = Field(default=5, ge=1, le=50)
    weights: dict[str, float] | None = Field(
        default=None,
        description="Optional weights e.g. {'form': 0.5, 'fixtures': 0.3, 'value': 0.2}. Omit for defaults."
    )

      
class SimilarPlayersRequest(BaseModel):
    player_name: str = Field(min_length=2)
    same_position: bool = True
    max_price: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=50)


class ComparePlayerRequest(BaseModel):
    names : list[str] = Field(min_length=2, max_length=5)