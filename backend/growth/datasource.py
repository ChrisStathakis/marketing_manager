"""Read-only client for the public catchandstats.com API.

The site is never written to from here: the growth tools only read the same
public JSON the site itself uses. Responses are cached on disk (default 6
hours) so a card studio session costs a handful of requests, not one per click.

Set ``CATCHANDSTATS_API_BASE`` to point at a staging copy, and
``GROWTH_CACHE_DIR`` / ``GROWTH_CACHE_TTL_HOURS`` to control the cache.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings

from .metrics import as_float

DEFAULT_BASE = "https://catchandstats.com/api"
USER_AGENT = "catchandstats-growth/1.0 (+https://catchandstats.com)"
PAGE_SIZE = 500
MAX_PAGES = 40
CACHE_VERSION = 3
TEAM_CACHE_VERSION = 1

#: HTTP statuses worth another attempt. Everything else in the 4xx range is a
#: bug on our side (bad parameter, bad season) and retrying only wastes time.
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3

#: Clubs from the four markets the growth plan prioritises. Matched as
#: case-insensitive fragments, because the API uses sponsored names
#: ("Fenerbahce Tarfin Istanbul", "Panathinaikos AKTOR Athens", ...).
PRIORITY_TEAMS: dict[str, tuple[str, ...]] = {
    "GR": ("Olympiacos", "Panathinaikos", "AEK", "Aris", "PAOK"),
    "TR": ("Fenerbahce", "Anadolu Efes", "Besiktas"),
    "RS": ("Crvena Zvezda", "Partizan"),
    "LT": ("Zalgiris",),
}

COUNTRY_LABELS = {
    "GR": "Greece",
    "TR": "Türkiye",
    "RS": "Serbia",
    "LT": "Lithuania",
}


class DatasourceError(RuntimeError):
    """The public API could not be reached or returned something unusable.

    ``status`` carries the HTTP status when there was one, and ``transient``
    says whether retrying later could plausibly help. The views only need the
    message, but callers that hold a cache want the distinction: a 502 with a
    cache entry behind it is a warning, a 400 is a configuration bug.
    """

    def __init__(self, message: str, status: int | None = None, transient: bool = False):
        super().__init__(message)
        self.status = status
        self.transient = transient


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    """Seconds from a ``Retry-After`` header, when it is a plain number."""
    headers = getattr(exc, "headers", None)
    raw = headers.get("Retry-After") if hasattr(headers, "get") else None
    if raw is None:
        return None
    try:
        # An HTTP-date form is legal but rare here; fall back to backoff.
        return max(0.0, min(float(raw), 30.0))
    except (TypeError, ValueError):
        return None


def _backoff(attempt: int) -> float:
    """Exponential-ish backoff with jitter, so two cards never retry in step."""
    return min(8.0, 0.6 * (attempt + 1)) * (1 + random.random() * 0.25)



def priority_country(team_name: str | None) -> str | None:
    """Return the priority market code for a club name, if it has one.

    Fragments are matched on word boundaries: ``"aris"`` must not match
    ``"Paris Basketball"``, which is exactly the false positive that made the
    Greek market filter useless.
    """
    lowered = (team_name or "").lower()
    for country, fragments in PRIORITY_TEAMS.items():
        for fragment in fragments:
            if re.search(rf"(?<![a-z]){re.escape(fragment.lower())}(?![a-z])", lowered):
                return country
    return None


def cache_dir() -> Path:
    configured = os.environ.get("GROWTH_CACHE_DIR") or getattr(settings, "GROWTH_CACHE_DIR", None)
    path = Path(configured) if configured else Path(settings.MEDIA_ROOT) / "growth-cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_cache(key: str, ttl_seconds: int, allow_stale: bool = False) -> tuple[dict | None, bool]:
    """Read a cache entry as ``(payload, stale)``.

    ``ttl_seconds=0`` means "ignore the TTL": used by the fallback path, where
    a day-old table is still better than no table at all.
    """
    path = cache_dir() / key
    if not path.exists():
        return None, False
    age = time.time() - path.stat().st_mtime
    if ttl_seconds and age > ttl_seconds:
        if not allow_stale:
            return None, False
        stale = True
    else:
        stale = False
    try:
        return json.loads(path.read_text(encoding="utf-8")), stale
    except (OSError, json.JSONDecodeError):
        return None, False


def _write_cache(key: str, payload: dict) -> None:
    path = cache_dir() / key
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        # A read-only media directory must not break card generation.
        pass


class CatchAndStatsClient:
    """Thin JSON client with retries, pagination and a disk cache."""

    def __init__(self, base_url: str | None = None, timeout: int | None = None, cache_ttl: int | None = None):
        self.base_url = (base_url or os.environ.get("CATCHANDSTATS_API_BASE") or DEFAULT_BASE).rstrip("/")
        self.timeout = timeout or int(os.environ.get("CATCHANDSTATS_TIMEOUT", "45"))
        self.cache_ttl = (
            cache_ttl if cache_ttl is not None else int(os.environ.get("GROWTH_CACHE_TTL_HOURS", "6")) * 3600
        )
        #: Non-fatal problems collected during a request (truncated pagination,
        #: a stale cache serving real numbers). Surfaced as the table warning.
        self.warnings: list[str] = []

    # -- transport ---------------------------------------------------------
    def get(self, path: str, **params) -> dict:
        cleaned = {key: value for key, value in params.items() if value is not None}
        cleaned.setdefault("format", "json")
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(cleaned)}"

        for attempt in range(MAX_ATTEMPTS):
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            last = attempt == MAX_ATTEMPTS - 1
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                # HTTPError subclasses URLError, so it has to come first.
                error = DatasourceError(
                    f"{url} answered HTTP {exc.code}",
                    status=exc.code,
                    transient=exc.code in RETRY_STATUSES,
                )
                if last or not error.transient:
                    raise error from exc
                time.sleep(_retry_after(exc) or _backoff(attempt))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                error = DatasourceError(f"Could not reach {url}: {exc}", transient=True)
                if last:
                    raise error from exc
                time.sleep(_backoff(attempt))
            except json.JSONDecodeError as exc:
                # An HTML error page or a captive portal will not fix itself.
                raise DatasourceError(f"{url} did not return JSON: {exc}") from exc
        raise DatasourceError(f"Could not read {url}")  # pragma: no cover - loop always returns or raises

    def paginate(self, path: str, **params) -> list[dict]:
        rows: list[dict] = []
        page = 1
        while page <= MAX_PAGES:
            payload = self.get(path, page=page, page_size=PAGE_SIZE, **params)
            if isinstance(payload, list):
                return payload
            batch = payload.get("results") or []
            rows.extend(batch)
            if not payload.get("next") or not batch:
                break
            page += 1
        else:
            self.warnings.append(f"{path}: stopped after {MAX_PAGES} pages, results may be incomplete")
        return rows

    # -- reference data ----------------------------------------------------
    def seasons(self, refresh: bool = False) -> list[dict]:
        """The season list, cached like the tables so the studio opens offline."""
        key = f"seasons-v{CACHE_VERSION}.json"
        if not refresh:
            cached, _ = _read_cache(key, self.cache_ttl)
            if cached and isinstance(cached.get("rows"), list):
                return cached["rows"]
        try:
            payload = self.get("/teams/seasons/list/")
        except DatasourceError:
            fallback, _ = _read_cache(key, 0)
            if fallback and isinstance(fallback.get("rows"), list):
                self.warnings.append("the season list came from the cache")
                return fallback["rows"]
            raise
        rows = payload.get("results", payload) if isinstance(payload, dict) else payload
        rows = sorted(rows or [], key=lambda row: row.get("id") or 0, reverse=True)
        _write_cache(key, {"rows": rows, "fetched_at": datetime.now(dt_timezone.utc).isoformat(timespec="seconds")})
        return rows

    @staticmethod
    def resolve_season(seasons: list[dict], season: str | int | None) -> dict:
        if not seasons:
            raise DatasourceError("The season list came back empty.")
        if season in (None, "", "current"):
            for row in seasons:
                if row.get("default_season") or row.get("active"):
                    return row
            return seasons[0]
        wanted = str(season).strip()
        for row in seasons:
            candidates = {str(row.get("id")), str(row.get("season_id")), str(row.get("title"))}
            if wanted in candidates:
                return row
        raise DatasourceError(f"Unknown season {season!r}.")

    # -- the one call everything else uses ---------------------------------
    def season_table(self, season: str | int | None = None, refresh: bool = False) -> dict:
        """Merge player-season rows with the extra analytics fields.

        ``/players/player-team-season/?season=<pk>`` already carries most
        metrics and, crucially, the player and club names. The analytics
        endpoint adds the proprietary extras (home-court advantage, beta,
        R², custom efficiency), so it is merged in by ``player_team_season``.
        """
        target = self.resolve_season(self.seasons(), season)
        key = f"season-{target['id']}-v{CACHE_VERSION}.json"
        if not refresh:
            cached, _ = _read_cache(key, self.cache_ttl)
            if cached:
                cached.setdefault("stale", False)
                cached.setdefault("warning", "")
                return cached

        try:
            player_rows = self.paginate("/players/player-team-season/", season=target["id"])
            analytics = self.paginate("/analytics/player-team-season-analytics/")
            team_rows = [
                row
                for row in self.paginate("/teams/team-season/list/")
                if row.get("season_title") == target.get("title")
            ]
        except DatasourceError as exc:
            fallback, _ = _read_cache(key, 0)
            if fallback:
                fallback = dict(fallback)
                fallback["stale"] = True
                fallback["warning"] = (
                    f"The public data API is not answering ({exc}). "
                    f"Showing the cached numbers from {fallback.get('fetched_at', 'an earlier run')}."
                )
                return fallback
            raise

        extras = {
            row.get("player_team_season"): row
            for row in analytics
            if row.get("player_team_season") is not None
        }

        players = []
        for row in player_rows:
            merged = dict(row)
            for name, value in (extras.get(row.get("id")) or {}).items():
                merged.setdefault(name, value)
            player = self._normalise(merged)
            if player["player"]:
                players.append(player)

        if not players:
            raise DatasourceError(
                f"The API returned no players for {target.get('title') or target.get('id')}. "
                "The season may not have started yet."
            )

        table = {
            "season": {
                "id": target.get("id"),
                "season_id": target.get("season_id"),
                "title": target.get("title"),
            },
            "players": players,
            "teams": team_rows,
            "fetched_at": datetime.now(dt_timezone.utc).isoformat(timespec="seconds"),
            "source": self.base_url,
            "stale": False,
            "warning": "; ".join(self.warnings),
        }
        _write_cache(key, table)
        return table

    # -- team-level advanced table -----------------------------------------
    def _team_reference_rows(self, target: dict, refresh: bool = False) -> list[dict]:
        key = f"team-season-{target['id']}-v{TEAM_CACHE_VERSION}.json"
        if not refresh:
            cached, _ = _read_cache(key, self.cache_ttl)
            if cached and isinstance(cached.get("rows"), list):
                return cached["rows"]
        try:
            rows = self.paginate("/teams/team-season/list/", season=target["id"])
        except DatasourceError as exc:
            fallback, _ = _read_cache(key, 0)
            if fallback and isinstance(fallback.get("rows"), list):
                self.warnings.append("the team list came from the cache")
                return fallback["rows"]
            raise exc
        _write_cache(
            key,
            {
                "rows": rows,
                "fetched_at": datetime.now(dt_timezone.utc).isoformat(timespec="seconds"),
            },
        )
        return rows

    def _team_game_rows(self, target: dict, refresh: bool = False) -> list[dict]:
        key = f"team-games-{target['id']}-v{TEAM_CACHE_VERSION}.json"
        if not refresh:
            cached, _ = _read_cache(key, self.cache_ttl)
            if cached and isinstance(cached.get("rows"), list):
                return cached["rows"]
        try:
            rows = self.paginate(
                "/games/game-team-list/",
                season=target["id"],
                game__is_played="true",
            )
        except DatasourceError as exc:
            fallback, _ = _read_cache(key, 0)
            if fallback and isinstance(fallback.get("rows"), list):
                self.warnings.append("the team game log came from the cache")
                return fallback["rows"]
            raise exc
        _write_cache(
            key,
            {
                "rows": rows,
                "fetched_at": datetime.now(dt_timezone.utc).isoformat(timespec="seconds"),
            },
        )
        return rows

    @staticmethod
    def _mean(values: list[float]) -> float | None:
        usable = [value for value in values if value is not None]
        return sum(usable) / len(usable) if usable else None

    def team_advanced_table(self, season: str | int | None = None, refresh: bool = False) -> dict:
        """Team four factors, record and ratings, computed from played games.

        The public team-season endpoint carries ORtg/DRtg/Pace, but not wins,
        TS%, eFG% or TOV%. The per-game team rows carry all of them. The site's
        own Team Advanced page averages the per-game ratings (not the
        possession-weighted season figure), so this does the same: that is what
        makes the numbers match the report the plan was built from.
        """
        target = self.resolve_season(self.seasons(), season)
        key = f"team-advanced-{target['id']}-v{TEAM_CACHE_VERSION}.json"
        if not refresh:
            cached, _ = _read_cache(key, self.cache_ttl)
            if cached:
                cached.setdefault("stale", False)
                cached.setdefault("warning", "")
                return cached

        try:
            references = self._team_reference_rows(target, refresh=refresh)
            games = self._team_game_rows(target, refresh=refresh)
        except DatasourceError as exc:
            fallback, _ = _read_cache(key, 0)
            if fallback:
                fallback = dict(fallback)
                fallback["stale"] = True
                fallback["warning"] = (
                    f"The public data API is not answering ({exc}). "
                    f"Showing the cached team table from {fallback.get('fetched_at', 'an earlier run')}."
                )
                return fallback
            raise

        references_by_id = {str(row.get("team")): row for row in references}
        buckets: dict[str, dict] = {}

        for row in games:
            team_id = str(row.get("team") or "")
            if not team_id:
                continue
            points = as_float(row.get("standingScore"))
            allowed = as_float(row.get("allowed_points"))
            # Unplayed fixtures come back as 0-0 and still carry win_status=true.
            if points is None or allowed is None or (points <= 0 and allowed <= 0):
                continue
            bucket = buckets.setdefault(
                team_id,
                {
                    "team_id": row.get("team"),
                    "team_title": row.get("team_name") or "",
                    "games": 0,
                    "wins": 0,
                    "losses": 0,
                    "points": 0.0,
                    "fga": 0.0,
                    "fta": 0.0,
                    "fgm": 0.0,
                    "fgm3": 0.0,
                    "turnovers": 0.0,
                    "ortg": [],
                    "drtg": [],
                    "pace": [],
                    "oreb_pct": [],
                },
            )
            bucket["games"] += 1
            if row.get("win_status"):
                bucket["wins"] += 1
            else:
                bucket["losses"] += 1
            bucket["points"] += points
            bucket["fga"] += as_float(row.get("field_goals_attempted_total")) or 0.0
            bucket["fta"] += as_float(row.get("free_throws_attempted")) or 0.0
            bucket["fgm"] += as_float(row.get("field_goals_made_total")) or 0.0
            bucket["fgm3"] += as_float(row.get("field_goals_made_three")) or 0.0
            bucket["turnovers"] += as_float(row.get("turnovers")) or 0.0
            for source, field in (("ortg", "offensive_rating"), ("drtg", "defensive_rating"), ("pace", "pace")):
                value = as_float(row.get(field))
                if value is not None and value > 0:
                    bucket[source].append(value)
            orb = as_float(row.get("orb_pct"))
            if orb is not None:
                bucket["oreb_pct"].append(orb)

        teams = []
        for team_id, bucket in buckets.items():
            reference = references_by_id.get(team_id, {})
            name = reference.get("team_title") or bucket.get("team_title") or f"Team {team_id}"
            fga, fta, tov = bucket["fga"], bucket["fta"], bucket["turnovers"]
            possessions = fga + 0.44 * fta
            ts_pct = bucket["points"] / (2 * possessions) if possessions else None
            efg_pct = (bucket["fgm"] + 0.5 * bucket["fgm3"]) / fga if fga else None
            tov_pct = tov / (possessions + tov) if possessions + tov else None
            ortg = self._mean(bucket["ortg"])
            drtg = self._mean(bucket["drtg"])
            if ortg is None:
                ortg = as_float(reference.get("offensive_rating"))
            if drtg is None:
                drtg = as_float(reference.get("defensive_rating"))
            teams.append(
                {
                    "team_id": bucket.get("team_id"),
                    "team_title": name,
                    "season_title": target.get("title"),
                    "games": bucket["games"],
                    "wins": bucket["wins"],
                    "losses": bucket["losses"],
                    "record": f"{bucket['wins']}-{bucket['losses']}",
                    "offensive_rating": ortg,
                    "defensive_rating": drtg,
                    "net_rating": round(ortg - drtg, 2) if ortg is not None and drtg is not None else None,
                    "avg_pace": self._mean(bucket["pace"]),
                    "ts_pct": ts_pct,
                    "efg_pct": efg_pct,
                    "tov_pct": tov_pct,
                    "oreb_pct": self._mean(bucket["oreb_pct"]),
                }
            )

        teams.sort(
            key=lambda team: (
                team["wins"],
                team["net_rating"] if team["net_rating"] is not None else -999,
            ),
            reverse=True,
        )
        table = {
            "season": {
                "id": target.get("id"),
                "season_id": target.get("season_id"),
                "title": target.get("title"),
            },
            "teams": teams,
            "fetched_at": datetime.now(dt_timezone.utc).isoformat(timespec="seconds"),
            "source": self.base_url,
            "stale": False,
            "warning": "; ".join(self.warnings),
        }
        _write_cache(key, table)
        return table

    def previous_team_advanced_table(self, season: str | int | None = None) -> dict:
        """The season before the selected one, for the "then vs now" notes."""
        season_rows = sorted(self.seasons(), key=lambda row: row.get("id") or 0, reverse=True)
        current = self.resolve_season(season_rows, season)
        older = [row for row in season_rows if (row.get("id") or 0) < (current.get("id") or 0)]
        if not older:
            return {
                "season": None,
                "teams": [],
                "fetched_at": None,
                "source": self.base_url,
                "stale": False,
                "warning": "No previous season is available.",
            }
        return self.team_advanced_table(older[0]["id"])

    @staticmethod
    def _normalise(row: dict) -> dict:
        metrics = {}
        for name, value in row.items():
            number = as_float(value)
            if number is not None:
                metrics[name] = number
        return {
            "id": row.get("id"),
            "player_id": row.get("player"),
            "player": (row.get("player_name") or "").strip(),
            "team": (row.get("team_name") or "").strip(),
            "season": row.get("season_name") or "",
            "season_id": row.get("season_id") or "",
            "position": row.get("position_title") or "",
            "country": priority_country(row.get("team_name")),
            "metrics": metrics,
        }


# -- module level helpers --------------------------------------------------
def season_table(season: str | int | None = None, refresh: bool = False) -> dict:
    return CatchAndStatsClient().season_table(season=season, refresh=refresh)


def team_advanced_table(season: str | int | None = None, refresh: bool = False) -> dict:
    return CatchAndStatsClient().team_advanced_table(season=season, refresh=refresh)


def previous_team_advanced_table(season: str | int | None = None) -> dict:
    return CatchAndStatsClient().previous_team_advanced_table(season=season)


def find_team(table: dict, team: str | int | None = None) -> dict | None:
    """Find a team row by id, full name or a distinctive fragment."""
    if team in (None, ""):
        return None
    needle = str(team).strip().lower()
    for row in table.get("teams", []):
        candidates = {
            str(row.get("team_id")),
            str(row.get("id")),
            (row.get("team_title") or "").lower(),
        }
        if needle in candidates:
            return row
        if needle and needle in (row.get("team_title") or "").lower():
            return row
    return None


def seasons(refresh: bool = False) -> list[dict]:
    return CatchAndStatsClient().seasons(refresh=refresh)


def find_player(table: dict, player_id: str | int | None) -> dict | None:
    if player_id in (None, ""):
        return None
    wanted = str(player_id)
    for row in table.get("players", []):
        if str(row.get("id")) == wanted or str(row.get("player_id")) == wanted:
            return row
    return None


def search_players(table: dict, query: str = "", country: str | None = None, metric: str | None = None) -> list[dict]:
    rows = table.get("players", [])
    needle = (query or "").strip().lower()
    if needle:
        rows = [row for row in rows if needle in row["player"].lower() or needle in row["team"].lower()]
    if country:
        rows = [row for row in rows if row.get("country") == country]
    if metric:
        rows = [row for row in rows if row["metrics"].get(metric) is not None]
    return rows
