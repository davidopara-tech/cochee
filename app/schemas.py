from pydantic import BaseModel, Field


class TopPlayersRequest(BaseModel):
    position: int | None = Field(default=None, ge=1, le=4)
    team: str | None = Field(default=None, min_length=2, max_length=4)
    max_price: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=50)
    weights: dict[str, float] | None = None
    min_ownership: float | None = Field(default=None, ge=0, le=100)
    max_ownership: float | None = Field(default=None, ge=0, le=100)
    


class SimilarPlayersRequest(BaseModel):
    player_name: str = Field(min_length=2)
    same_position: bool = True
    max_price: int | None = Field(default=None, gt=0)
    limit: int = Field(default=5, ge=1, le=50)


class ComparePlayerRequest(BaseModel):
    names : list[str] = Field(min_length=2, max_length=5)