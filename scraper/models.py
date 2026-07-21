"""Typed records for every scraped entity (see spec §3)."""
from dataclasses import dataclass, field


@dataclass
class Captain:
    player_id: str
    name: str
    player_url: str


@dataclass
class Team:
    id: str
    slug: str
    profile_url: str
    flag_url: str | None
    country: str
    team_name: str | None
    faculty: str | None
    group: str
    captain: Captain | None = None


@dataclass
class Player:
    player_id: str
    slug: str
    player_url: str
    jersey_number: str | None
    name: str
    role: str | None
    is_captain: bool
    photo_url: str | None
    goals: int
    assists: int
    cards: int


@dataclass
class Roster:
    team_id: str
    country: str
    team_name: str | None
    players: list[Player] = field(default_factory=list)


@dataclass
class FixtureSide:
    country: str
    flag_code: str | None


@dataclass
class Fixture:
    match_id: str
    slug: str
    match_url: str
    match_no: int | None
    group: str | None
    date: str | None
    time: str | None
    datetime_iso: str | None
    home: FixtureSide
    away: FixtureSide
    home_score: int | None
    away_score: int | None
    status: str
    raw_score: str


@dataclass
class StandingRow:
    position: int
    team_id: str | None
    country: str
    team_url: str | None
    played: int
    points: int
    goal_diff: int
    goals_for: int
    fair_play: int
    qualified: bool


@dataclass
class GroupStanding:
    group: str
    table: list[StandingRow] = field(default_factory=list)


@dataclass
class Scorer:
    rank: int
    player_id: str | None
    name: str
    team: str | None
    goals: int


@dataclass
class KnockoutMatch:
    match_no: int | None
    next_match_no: int | None
    match_url: str | None
    stage: str
    home_label: str | None
    away_label: str | None
    home_team: str | None
    away_team: str | None
    home_score: int | None
    away_score: int | None
    status: str


@dataclass
class BracketStage:
    stage: str
    matches: list[KnockoutMatch] = field(default_factory=list)
