"""SQLAlchemy models for Cochee."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    """Add creation and update timestamps to a model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class Team(TimestampMixin, Base):
    """Premier League team data from FPL's bootstrap endpoint."""

    __tablename__ = "teams"

    # FPL IDs are stable across data syncs and serve as primary keys.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    short_name: Mapped[str] = mapped_column(String(10), nullable=False)

    strength: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_overall_home: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_overall_away: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_attack_home: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_attack_away: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_defence_home: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_defence_away: Mapped[int] = mapped_column(Integer, nullable=False)

    players: Mapped[list["Player"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Team {self.short_name} ({self.name})>"


class Gameweek(TimestampMixin, Base):
    """Gameweek and deadline data from FPL's bootstrap endpoint."""

    __tablename__ = "gameweeks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # FPL publishes deadlines in UTC; preserve timezone information.
    deadline_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    is_current: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_next: Mapped[bool] = mapped_column(nullable=False, default=False)
    finished: Mapped[bool] = mapped_column(nullable=False, default=False)

    data_checked: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Gameweek {self.id} {self.name}>"


class Fixture(TimestampMixin, Base):
    """Fixture and result data from FPL's fixtures endpoint."""

    __tablename__ = "fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # FPL may not have assigned a gameweek yet, e.g. for postponed fixtures.
    gameweek_id: Mapped[int | None] = mapped_column(
        ForeignKey("gameweeks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    home_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    away_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kickoff_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FPL fixture difficulty: 1 is easiest, 5 is hardest.
    team_h_difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    team_a_difficulty: Mapped[int] = mapped_column(Integer, nullable=False)

    team_h_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_a_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    finished: Mapped[bool] = mapped_column(nullable=False, default=False)
    started: Mapped[bool | None] = mapped_column(nullable=True)
    finished_provisional: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<Fixture {self.id} GW{self.gameweek_id} "
            f"T{self.home_team_id} vs T{self.away_team_id}>"
        )

class Player(TimestampMixin, Base):
    """Player data and similarity-search embeddings from FPL."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    second_name: Mapped[str] = mapped_column(String(100), nullable=False)
    web_name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # FPL position codes: 1=GK, 2=DEF, 3=MID, 4=FWD.
    element_type: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    search_name: Mapped[str] = mapped_column(String(200), index=True)
    
    # FPL status codes include available, injured, doubtful, and suspended.
    status: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    
    news: Mapped[str | None] = mapped_column(String(500), nullable=True)
   
    # FPL uses NULL to mean fully fit.
    chance_of_playing_this_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chance_of_playing_next_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # FPL prices are stored in tenths of a million (61 = £6.1m).
    now_cost: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    cost_change_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_change_event: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_by_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    points_per_game: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clean_sheets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_conceded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yellow_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    form: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    form_weighted: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    event_points: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Expected-stat fields are per-90 rates.
    expected_goals_per_90: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_assists_per_90: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_goal_involvements_per_90: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    expected_goals_conceded_per_90: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    ict_index: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    influence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    creativity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    threat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    penalties_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direct_freekicks_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corners_and_indirect_freekicks_order: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Computed after ingestion; nullable until the embedding job runs.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(24), nullable=True
    )

    team: Mapped["Team"] = relationship(back_populates="players")
    

    def __repr__(self) -> str:
        return f"<Player {self.id} {self.web_name} (team={self.team_id})>"