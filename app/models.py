# app/models.py
"""
SQLAlchemy models for Cochee.

Conventions used across ALL models:
  - Primary key is the FPL-supplied ID (not auto-increment), so re-ingesting
    data uses UPSERT cleanly: INSERT ... ON CONFLICT (id) DO UPDATE.
  - Every table inherits from Base (defined in app/database.py).
  - Every table includes created_at / updated_at via TimestampMixin.
"""

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
from pgvector.sqlalchemy import Vector  

# ---------------------------------------------------------------------------
# DRY: TimestampMixin
# ---------------------------------------------------------------------------
class TimestampMixin:
    """
    Adds created_at / updated_at columns to any model that mixes it in.

    Why a mixin? Because writing these two columns on every table would
    be repetitive and error-prone. With the mixin, every table gets them
    for free and behaviour stays consistent.

    server_default=func.now() -> Postgres fills the value on insert.
    onupdate=func.now()       -> Postgres refreshes it on every UPDATE.
    """

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

# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------
class Team(TimestampMixin, Base):
    """
    One Premier League club (Arsenal, Liverpool, Man City...).

    Source: FPL bootstrap-static endpoint, "teams" array.
    Row count: 20 (one per club). Almost never changes mid-season.
    """

    __tablename__ = "teams"

    # FPL's own team ID (1-20). We reuse it as our primary key so that
    # re-ingesting uses UPSERT on a stable identifier. No auto-increment.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # Full club name, e.g. "Arsenal".
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Three-letter abbreviation, e.g. "ARS". Useful for compact UI displays.
    short_name: Mapped[str] = mapped_column(String(10), nullable=False)

    # FPL's 1-5 difficulty ratings for this team's fixtures at each venue.
    # Higher = harder. Used by the Fixtures advisor.
    strength: Mapped[int] = mapped_column(Integer, nullable=False)               # overall
    strength_overall_home: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_overall_away: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_attack_home: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_attack_away: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_defence_home: Mapped[int] = mapped_column(Integer, nullable=False)
    strength_defence_away: Mapped[int] = mapped_column(Integer, nullable=False)

    # Python-side convenience: team.players returns all Player rows for this club.
    # "back_populates" pairs it with Player.team so both sides stay in sync.
    players: Mapped[list["Player"]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        # Makes debugging nicer: print(team) shows "<Team ARS (Arsenal)>"
        return f"<Team {self.short_name} ({self.name})>"


# ---------------------------------------------------------------------------
# Gameweek
# ---------------------------------------------------------------------------
class Gameweek(TimestampMixin, Base):
    """
    One FPL gameweek (GW1 ... GW38).

    Source: FPL bootstrap-static endpoint, "events" array.
    Row count: 38 (one per gameweek). The FPL season has exactly 38.

    A gameweek is the scoring unit of FPL: every manager picks a team,
    submits it before a deadline, and earns points from that gameweek's
    matches. Deadlines matter because transfers after the deadline count
    towards the NEXT gameweek.
    """

    __tablename__ = "gameweeks"

    # FPL's own gameweek ID (1-38). Reuse as primary key for UPSERT.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # Display name, e.g. "Gameweek 1". FPL sends this directly.
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # Deadline = the moment after which you can no longer make transfers
    # for this gameweek. Stored with timezone to avoid UTC/localtime bugs
    # (FPL deadlines are published in UTC and shift with BST/GMT).
    deadline_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Which gameweek are we currently in? FPL sets exactly one to True.
    is_current: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Which gameweek is next? FPL sets exactly one to True.
    # We use this to know which deadline the user is playing towards.
    is_next: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Has the gameweek fully finished? True once all matches are scored.
    finished: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Has the gameweek STARTED (first match kicked off)? Distinct from
    # finished: a gameweek can be started but not yet finished.
   

    # Optional: FPL's "data_checked" flag. True once the gameweek's points
    # have been confirmed and bonuses awarded. Safe to trust the numbers.
    data_checked: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Gameweek {self.id} {self.name}>"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------
class Fixture(TimestampMixin, Base):
    """
    One match between two teams in a specific gameweek.

    Source: FPL fixtures/ endpoint.
    Row count: ~380 per season (20 teams -> each plays 38, / 2 = 380).

    This table is the raw material for the Fixtures advisor. Given a player,
    we look at their team's next N fixtures and average the FPL difficulty
    ratings to answer "does this player have an easy run coming up?"
    """

    __tablename__ = "fixtures"

    # FPL's own fixture ID. Reuse as primary key for UPSERT.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # Which gameweek this match belongs to. Nullable because FPL sometimes
    # creates a fixture before assigning it to a gameweek (rare, usually
    # during schedule disruptions), and postponed matches have no GW.
    gameweek_id: Mapped[int | None] = mapped_column(
        ForeignKey("gameweeks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # The two teams. Home team listed first, away second — matches how FPL
    # reports it, and how we'll display it.
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

    # Kickoff timestamp. TZ-aware for the same reason as gameweek deadlines.
    kickoff_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FPL's difficulty rating for the HOME team in this specific match.
    # 1 = easiest, 5 = hardest. This is per-match, not per-team, because
    # difficulty depends on the opponent. Arsenal playing Man City = 5;
    # Arsenal playing Luton = 2. This is what the Fixtures advisor reads.
    team_h_difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    team_a_difficulty: Mapped[int] = mapped_column(Integer, nullable=False)

    # FPL's minute-by-minute score. Useful for "how did team X do last week"
    # questions and for displaying recent results. Null until the match starts.
    team_h_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team_a_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Has the match finished? FPL sets this once the final whistle blows
    # and points are tallied. A gameweek is finished only when ALL its
    # fixtures are finished.
    finished: Mapped[bool] = mapped_column(nullable=False, default=False)

    # Did the match actually kick off? A postponed match has finished=False
    # and started=False forever, until rescheduled.
    started: Mapped[bool | None] = mapped_column(nullable=True)

    # Has FPL confirmed the stats for this match? Same idea as gameweek's
    # data_checked — bonus points settled, assists corrected.
    finished_provisional: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __repr__(self) -> str:
        return (
            f"<Fixture {self.id} GW{self.gameweek_id} "
            f"T{self.home_team_id} vs T{self.away_team_id}>"
        )

# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------
class Player(TimestampMixin, Base):
    """
    One FPL footballer.

    Source: FPL bootstrap-static endpoint, "elements" array.
    Row count: ~700 (every player in the Premier League).

    This is the most important table in Cochee. It holds:
      1. Raw stats from FPL (form, points, price, xG, ICT...)
      2. A 24-feature embedding vector (added in part 2) used for
         semantic similarity search ("find players like Saka").

    All numeric fields that FPL sends as STRINGS (form="6.0", ict_index="10.6")
    are converted to floats during ingestion — not stored as strings here.
    """

    __tablename__ = "players"

    # FPL's own player ID. Reuse as PK for UPSERT. e.g. Raya = 1, Salah = 283.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)

    # Which Premier League club this player belongs to. Cascade on delete
    # (if a team is removed, its players go too).
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Identity -----------------------------------------------------------
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    second_name: Mapped[str] = mapped_column(String(100), nullable=False)
    web_name: Mapped[str] = mapped_column(String(100), nullable=False)  # "Salah"
    # FPL position code: 1=GK, 2=DEF, 3=MID, 4=FWD.
    # Stored as int to match FPL; the Position advisor maps it to a string.
    element_type: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # --- Status / availability ---------------------------------------------
    # FPL status code: 'a'=available, 'i'=injured, 'd'=doubtful,
    # 's'=suspended, 'u'=unavailable, 'n'=on loan.
    # Cochee filters to status='a' for recommendations.
    status: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    # Free-text injury/availability note from FPL. Null when fully fit.
    news: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 0-100 percent chance of playing this round. NULL means 100% (FPL quirk).
    chance_of_playing_this_round: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chance_of_playing_next_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Price / ownership --------------------------------------------------
    # Price in tenths of a million: 61 = £6.1m. FPL's native unit.
    now_cost: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Original season-start price, same unit.
    cost_change_start: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Price change this gameweek, same unit.
    cost_change_event: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Percentage of managers who own this player, e.g. 45.2 means 45.2%.
    selected_by_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # --- Season totals ------------------------------------------------------
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    points_per_game: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clean_sheets: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    goals_conceded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # bonus point system score
    yellow_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    red_cards: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    saves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # GKs only

    # --- Form / recent performance -----------------------------------------
    # FPL sends these as strings ("6.0"); ingestion converts to float.
    form: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Form weighted by minutes played. Less noisy than raw form.
    form_weighted: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Points scored in the current gameweek. Null before the gameweek ends.
    event_points: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Expected stats (xG / xA / xGI) ------------------------------------
    # These come from FPL as strings too. Per-90 rates, not totals.
    expected_goals_per_90: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_assists_per_90: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_goal_involvements_per_90: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    # Underlying stats per 90 (shots, chances created, etc.)
    expected_goals_conceded_per_90: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )

    # --- ICT Index ----------------------------------------------------------
    # FPL's own composite metric. Also sent as a string.
    ict_index: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    influence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    creativity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    threat: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # --- Set-piece duties ---------------------------------------------------
    # Order in the pecking order (1 = takes them). Null = doesn't take them.
    penalties_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direct_freekicks_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corners_and_indirect_freekicks_order: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
         # --- Vector embedding (pgvector) ----------------------------------------
    # A 24-dimensional vector capturing the player's whole profile:
    # position, price, form, xG, xA, ICT, ownership, fixture difficulty,
    # set-piece duties, availability, etc. (full list of 24 features is in
    # the project notes.)
    #
    # Two players with "close" vectors play alike statistically. This is
    # what lets Cochee answer "find me a cheaper Saka" — we take Saka's
    # vector, find the nearest neighbours in this column, filter out anyone
    # priced higher, and we've got our answer.
    #
    # Nullable because we ingest players from FPL FIRST, then compute their
    # embeddings in a second pass. Until that second pass runs, the value
    # is NULL.
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(24), nullable=True
    )

    # --- Relationships ------------------------------------------------------
    # Python-side shortcut: player.team gives us the Team object directly,
    # no manual join needed. back_populates pairs with Team.players.
    team: Mapped["Team"] = relationship(back_populates="players")

    def __repr__(self) -> str:
        return f"<Player {self.id} {self.web_name} (team={self.team_id})>"