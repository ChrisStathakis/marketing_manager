"""Turn API rows into card specs.

A *spec* is plain JSON: title, subtitle, optional headline, a list of rows and
optional comparison columns. ``cards.render_card`` draws it, ``captions``
turns it into text. Keeping this layer pure means the same numbers can be
previewed, saved, captioned and re-used without touching the network.

Naming licence: the API stores players as ``"VEZENKOV, SASHA"``. Cards show
"Ulanovas, Edgaras" as "Edgaras Ulanovas", which is what people search for.
"""

from __future__ import annotations

from datetime import date

from .datasource import COUNTRY_LABELS, find_player, find_team, priority_country
from .metrics import (
    DEFAULT_PLAYER_METRICS,
    METRICS,
    STORY_METRICS,
    TEAM_METRICS,
    as_float,
    format_metric,
    is_better,
    is_plausible,
    metric_label,
)

ACCENT = "#34d399"
ACCENT_WARM = "#fbbf24"

#: Enough games and minutes to keep a cameo off a leaderboard. Early in a
#: season these fall back to 1 game / 0 minutes rather than showing nothing.
MIN_GAMES = 3
MIN_MINUTES = 10.0

_CONTEXT_METRICS = ("score", "ts_pct", "usage_pct", "per", "consistency_score")

#: Sponsored club names -> the name people actually chant. Longest first.
TEAM_SHORTS = (
    ("Anadolu Efes", "Anadolu Efes"),
    ("Crvena Zvezda", "Crvena Zvezda"),
    ("Real Madrid", "Real Madrid"),
    ("FC Barcelona", "Barcelona"),
    ("Panathinaikos", "Panathinaikos"),
    ("Olympiacos", "Olympiacos"),
    ("Fenerbahce", "Fenerbahçe"),
    ("Besiktas", "Beşiktaş"),
    ("Partizan", "Partizan"),
    ("Zalgiris", "Žalgiris"),
    ("Baskonia", "Baskonia"),
    ("ASVEL", "ASVEL"),
    ("Maccabi", "Maccabi"),
    ("Hapoel", "Hapoel"),
    ("Bayern", "Bayern"),
    ("Armani", "Olimpia Milano"),
    ("Virtus", "Virtus Bologna"),
    ("Valencia", "Valencia"),
    ("Paris", "Paris"),
    ("Dubai", "Dubai"),
)


def team_short(name: str | None) -> str:
    lowered = (name or "").lower()
    for fragment, short in TEAM_SHORTS:
        if fragment.lower() in lowered:
            return short
    return (name or "").split(" ")[0] if name else "TBD"


def display_name(raw: str) -> str:
    """'VEZENKOV, SASHA' -> 'Sasha Vezenkov'."""
    text = (raw or "").strip()
    if not text:
        return "Unknown player"
    if "," in text:
        last, first = (part.strip() for part in text.split(",", 1))
        return f"{first.title()} {last.title()}".strip()
    return text.title()


def short_name(raw: str) -> str:
    """Last name only, for tight two-column layouts."""
    text = (raw or "").strip()
    if "," in text:
        text = text.split(",", 1)[0]
    elif " " in text:
        text = text.split(" ", 1)[-1]
    return text.title()


def season_short(title: str | None) -> str:
    """'2026-2027' -> '2026-27'."""
    parts = (title or "").split("-")
    if len(parts) == 2 and len(parts[1]) == 4:
        return f"{parts[0]}-{parts[1][2:]}"
    return title or ""


def value_of(row: dict, key: str):
    """Players keep numbers under ``metrics``; team rows are flat."""
    if row is None:
        return None
    return (row.get("metrics") or {}).get(key, row.get(key))


def _footer() -> str:
    return "Advanced EuroLeague data · catchandstats.com"


def _ranked(
    table: dict,
    key: str,
    country: str | None = None,
    min_games: int = MIN_GAMES,
    min_minutes: float = MIN_MINUTES,
) -> list[dict]:
    direction = METRICS.get(key).direction if key in METRICS else 1

    def collect(games: int, minutes: float) -> list[dict]:
        rows = []
        for player in table.get("players", []):
            raw = player["metrics"].get(key)
            if not is_plausible(key, raw):
                continue
            if country and player.get("country") != country:
                continue
            player_games = as_float(player["metrics"].get("games"))
            if player_games is not None and player_games < games:
                continue
            playing_time = as_float(player["metrics"].get("time_played"))
            if playing_time is not None and playing_time < minutes:
                continue
            rows.append(player)
        rows.sort(key=lambda row: row["metrics"][key], reverse=direction == 1)
        return rows

    rows = collect(min_games, min_minutes)
    if not rows and (min_games > 1 or min_minutes > 0):
        rows = collect(1, 0)
    return rows


def rank_of(table: dict, player: dict, key: str) -> tuple[int | None, int]:
    ranked = _ranked(table, key, country=None)
    for index, row in enumerate(ranked, start=1):
        if row.get("id") == player.get("id"):
            return index, len(ranked)
    return None, len(ranked)


def _games_note(table: dict) -> str:
    games = max(
        (as_float(player["metrics"].get("games")) or 0 for player in table.get("players", [])),
        default=0,
    )
    return f"after {int(games)} games" if games else "season to date"


def _country_note(row: dict) -> str:
    label = COUNTRY_LABELS.get(row.get("country") or "")
    return f"{label} · {row['team']}" if label else row["team"]


def build_player_card(row: dict, keys: tuple[str, ...] | None = None, headline_key: str | None = None) -> dict:
    keys = tuple(keys or DEFAULT_PLAYER_METRICS)
    headline_key = headline_key or next((key for key in keys if value_of(row, key) is not None), "score")
    row_keys = [key for key in keys if key != headline_key][:4]
    return {
        "kind": "player",
        "title": display_name(row["player"]),
        "subtitle": f"{_country_note(row)} · {season_short(row['season'])}",
        "headline": format_metric(headline_key, value_of(row, headline_key)),
        "headline_label": metric_label(headline_key),
        "headline_key": headline_key,
        "rows": [
            {"key": key, "label": metric_label(key), "value": format_metric(key, value_of(row, key))}
            for key in row_keys
        ],
        "footer": _footer(),
        "accent": ACCENT,
    }


def build_metric_card(
    row: dict,
    key: str,
    rank: int | None = None,
    total: int | None = None,
    title: str | None = None,
) -> dict:
    note = f"#{rank} of {total} qualified players" if rank and total else ""
    contexts = [item for item in _CONTEXT_METRICS if item != key][:3]
    return {
        "kind": "metric",
        "eyebrow": "Metric of the day",
        "title": title or metric_label(key),
        "subtitle": f"{display_name(row['player'])} · {_country_note(row)}",
        "headline": format_metric(key, value_of(row, key)),
        "headline_label": metric_label(key),
        "headline_key": key,
        "headline_note": note,
        "rows": [
            {"key": item, "label": metric_label(item), "value": format_metric(item, value_of(row, item))}
            for item in contexts
        ],
        "footer": _footer(),
        "accent": ACCENT_WARM,
    }


def build_comparison_card(row_a: dict, row_b: dict, keys: tuple[str, ...] | None = None) -> dict:
    keys = tuple(keys or ("score", "ts_pct", "usage_pct", "per", "consistency_score"))
    rows = []
    for key in keys:
        left, right = value_of(row_a, key), value_of(row_b, key)
        winner = None
        if left is not None and right is not None:
            winner = "left" if is_better(key, left, right) else ("right" if is_better(key, right, left) else None)
        rows.append(
            {
                "key": key,
                "label": metric_label(key),
                "left": format_metric(key, left),
                "right": format_metric(key, right),
                "winner": winner,
            }
        )
    return {
        "kind": "comparison",
        "eyebrow": "Head to head",
        "title": f"{short_name(row_a['player'])} vs {short_name(row_b['player'])}",
        "subtitle": f"{row_a['team']} · {row_b['team']} · {season_short(row_a['season'])}",
        "columns": [display_name(row_a["player"]), display_name(row_b["player"])],
        "rows": rows,
        "footer": _footer(),
        "accent": ACCENT,
    }


def build_round_recap_card(table: dict, title: str | None = None) -> dict:
    """Five different players, each leading a different story metric."""
    used: set[int] = set()
    rows = []
    for key in STORY_METRICS:
        for player in _ranked(table, key):
            if player.get("id") in used:
                continue
            used.add(player.get("id"))
            rows.append(
                {
                    "key": key,
                    "label": display_name(player["player"]),
                    "value": format_metric(key, value_of(player, key)),
                    "note": f"{metric_label(key)} · {player['team']}",
                    "note_metric": key,
                    "note_team": player["team"],
                }
            )
            break
        if len(rows) == 5:
            break
    return {
        "kind": "round_recap",
        "eyebrow": "Round recap",
        "title": title or "Five numbers nobody is talking about",
        "subtitle": f"EuroLeague {season_short((table.get('season') or {}).get('title'))} · {_games_note(table)}",
        "rows": rows,
        "footer": _footer(),
        "accent": ACCENT,
    }


def _pick_team(table: dict, preferred: str | None = None, exclude: str | None = None) -> dict:
    teams = table.get("teams") or []
    if not teams:
        raise ValueError("No team rows for this season yet.")

    def matches(team: dict, needle: str) -> bool:
        return needle.lower() in (team.get("team_title") or "").lower()

    if preferred:
        for team in teams:
            if matches(team, preferred) and team.get("team_title") != exclude:
                return team
        raise ValueError(f"No team matching {preferred!r} in this season.")

    # Default: two priority clubs from different markets (Greece vs Türkiye).
    order = {code: index for index, code in enumerate(COUNTRY_LABELS)}
    ordered = sorted(teams, key=lambda team: order.get(priority_country(team.get("team_title")), 99))
    for team in ordered:
        if team.get("team_title") != exclude:
            return team
    return teams[0]


def build_matchup_card(team_a: dict, team_b: dict) -> dict:
    rows = []
    for key in TEAM_METRICS:
        left, right = value_of(team_a, key), value_of(team_b, key)
        winner = None
        if left is not None and right is not None:
            winner = "left" if is_better(key, left, right) else ("right" if is_better(key, right, left) else None)
        rows.append(
            {
                "key": key,
                "label": metric_label(key),
                "left": format_metric(key, left),
                "right": format_metric(key, right),
                "winner": winner,
            }
        )
    return {
        "kind": "matchup",
        "eyebrow": "Matchup",
        "title": f"{team_short(team_a.get('team_title'))} vs {team_short(team_b.get('team_title'))}",
        "subtitle": f"{season_short(team_a.get('season_title')) or 'This season'} · team profile",
        "columns": [team_a.get("team_title") or "Home", team_b.get("team_title") or "Away"],
        "rows": rows,
        "footer": _footer(),
        "accent": ACCENT,
    }


def _team_record(team: dict) -> str:
    if team.get("record"):
        return str(team["record"])
    wins, losses = team.get("wins"), team.get("losses")
    if wins is not None and losses is not None:
        return f"{wins}-{losses}"
    return ""


def _team_ranked(teams: list[dict]) -> list[dict]:
    """Record first, net rating second — the order the plan's table uses."""
    return sorted(
        teams,
        key=lambda team: (
            team.get("wins") or 0,
            team.get("net_rating") if team.get("net_rating") is not None else -999,
        ),
        reverse=True,
    )


def build_team_card(
    team: dict,
    previous: dict | None = None,
    rank: int | None = None,
    total: int | None = None,
) -> dict:
    """A four-factors profile slide for one club, with last season's number."""
    keys = ("offensive_rating", "defensive_rating", "ts_pct", "efg_pct", "tov_pct")
    rows = []
    for key in keys:
        value = value_of(team, key)
        prev_value = value_of(previous, key) if previous else None
        note = (
            f"last season {format_metric(key, prev_value)}"
            if prev_value is not None
            else ""
        )
        rows.append(
            {
                "key": key,
                "label": metric_label(key),
                "value": format_metric(key, value),
                "note": note,
            }
        )

    record = _team_record(team)
    headline_note = ""
    if rank:
        headline_note = f"#{rank} of {total}" if total else f"#{rank}"
        if record:
            headline_note += f" · {record}"
    elif record:
        headline_note = record

    return {
        "kind": "team",
        "eyebrow": "Team check",
        "title": team_short(team.get("team_title")),
        "subtitle": f"{team.get('team_title') or ''} · {season_short(team.get('season_title'))}".strip(" ·"),
        "headline": format_metric("net_rating", team.get("net_rating")),
        "headline_label": metric_label("net_rating"),
        "headline_key": "net_rating",
        "headline_note": headline_note,
        "rows": rows,
        "footer": _footer(),
        "accent": ACCENT,
        "team_id": team.get("team_id") or team.get("id"),
    }


def build_top8_table(
    teams: list[dict],
    *,
    top_n: int = 8,
    title: str | None = None,
    rounds: int | None = None,
) -> dict:
    """The one-slide table for Reddit/X, with eight rows and no dropped teams."""
    ranked = _team_ranked(teams)[: max(1, top_n)]
    if not ranked:
        raise ValueError("No team rows for this season yet.")
    games = rounds or max((team.get("games") or 0 for team in ranked), default=0)
    season = season_short(ranked[0].get("season_title"))
    rows = []
    for index, team in enumerate(ranked, start=1):
        net = team.get("net_rating")
        rows.append(
            {
                "rank": index,
                "team": team_short(team.get("team_title")),
                "team_full": team.get("team_title") or "",
                "record": _team_record(team),
                "net": format_metric("net_rating", net),
                "value": format_metric("net_rating", net),
                "label": team_short(team.get("team_title")),
                "note": f"{_team_record(team)} · {format_metric('net_rating', net)}".strip(" ·"),
                "team_id": team.get("team_id") or team.get("id"),
            }
        )
    default_title = f"Top {len(ranked)} — {season}" if season else f"Top {len(ranked)}"
    return {
        "kind": "top8",
        "layout": "table",
        "eyebrow": "Top 8",
        "title": title or default_title,
        "subtitle": f"Net rating · after {games} games" if games else "Net rating · season to date",
        "columns": ["#", "Team", "Rec", "Net"],
        "rows": rows,
        "footer": _footer(),
        "accent": ACCENT,
    }


def build_top8_carousel(
    teams: list[dict],
    *,
    top_n: int = 8,
    previous_teams: list[dict] | None = None,
    title: str | None = None,
    include_table: bool = False,
    include_cta: bool = True,
) -> list[dict]:
    """Cover + one slide per team (+ table/CTA), ready to render as a set."""
    ranked = _team_ranked(teams)[: max(1, top_n)]
    if not ranked:
        raise ValueError("No team rows for this season yet.")
    previous_by_key = {
        str(team.get("team_id") or team.get("team_title")): team
        for team in (previous_teams or [])
    }
    season = season_short(ranked[0].get("season_title"))
    games = max((team.get("games") or 0 for team in ranked), default=0)
    cover_title = title or (f"Top {len(ranked)} after {games} rounds" if games else f"Top {len(ranked)} — {season}")
    best = ranked[0]
    cover = {
        "kind": "top8",
        "eyebrow": "Top 8",
        "title": cover_title,
        "subtitle": f"{season} · record first, then net rating",
        "headline": format_metric("net_rating", best.get("net_rating")),
        "headline_label": metric_label("net_rating"),
        "headline_note": f"{team_short(best.get('team_title'))} · {_team_record(best)}".strip(" ·"),
        "rows": [
            {
                "key": "net_rating",
                "label": team_short(team.get("team_title")),
                "value": format_metric("net_rating", team.get("net_rating")),
                "note": _team_record(team),
            }
            for team in ranked[:3]
        ],
        "footer": _footer(),
        "accent": ACCENT,
    }
    specs = [cover]
    for index, team in enumerate(ranked, start=1):
        previous = previous_by_key.get(str(team.get("team_id") or team.get("team_title")))
        specs.append(build_team_card(team, previous=previous, rank=index, total=len(ranked)))
    if include_table:
        specs.append(build_top8_table(ranked, top_n=len(ranked), title=cover_title, rounds=games))
    if include_cta:
        specs.append(
            {
                "kind": "top8",
                "eyebrow": "Your turn",
                "title": "Which team keeps it up?",
                "subtitle": "Full profiles, four factors and last season's numbers.",
                "headline": "catchandstats.com",
                "headline_label": "All 20 teams",
                "rows": [],
                "footer": _footer(),
                "accent": ACCENT_WARM,
            }
        )
    return specs



def default_story(today: date | None = None) -> str:
    moment = today or date.today()
    return STORY_METRICS[moment.toordinal() % len(STORY_METRICS)]


def build_spec(
    table: dict,
    kind: str,
    *,
    player_id: str | int | None = None,
    opponent_id: str | int | None = None,
    metric: str | None = None,
    country: str | None = None,
    story: str | None = None,
    teams: list[str] | None = None,
    title: str | None = None,
    previous_table: dict | None = None,
    top_n: int = 8,
) -> dict:
    """Build the spec for any card kind, auto-picking what the caller omits."""
    if kind in ("team", "team_delta", "top8"):
        chosen = teams or []
        previous_by_key = {
            str(team.get("team_id") or team.get("team_title")): team
            for team in (previous_table or {}).get("teams", [])
        }
        if kind == "top8":
            return build_top8_table(
                table.get("teams") or [],
                top_n=top_n,
                title=title,
            )
        team_rows = _team_ranked(table.get("teams") or [])
        if chosen:
            team = find_team(table, chosen[0])
            if team is None:
                raise ValueError(f"No team matching {chosen[0]!r} in this season.")
        else:
            team = team_rows[0] if team_rows else _pick_team(table)
        rank = next(
            (
                index
                for index, row in enumerate(team_rows, start=1)
                if str(row.get("team_id") or row.get("team_title"))
                == str(team.get("team_id") or team.get("team_title"))
            ),
            None,
        )
        previous = previous_by_key.get(str(team.get("team_id") or team.get("team_title")))
        card = build_team_card(team, previous=previous, rank=rank, total=len(team_rows))
        if kind == "team_delta":
            card["kind"] = "team_delta"
            card["eyebrow"] = "Then vs now"
        return card

    explicit_story = story or metric
    story = explicit_story or default_story()
    if story not in METRICS:
        raise ValueError(f"Unknown metric {story!r}.")

    if kind == "matchup":
        chosen = teams or []
        team_a = _pick_team(table, chosen[0] if chosen else None)
        team_b = _pick_team(table, chosen[1] if len(chosen) > 1 else None, exclude=team_a.get("team_title"))
        return build_matchup_card(team_a, team_b)

    if kind == "round_recap":
        return build_round_recap_card(table, title=title)

    row = find_player(table, player_id)
    if row is None:
        ranked = _ranked(table, story, country=country)
        if not ranked:
            raise ValueError(f"No player has {metric_label(story)} in this season yet.")
        row = ranked[0]

    if kind == "player":
        # The rotating "story" metric becomes a supporting row; the headline
        # stays the overall rating unless the caller asked for a metric.
        keys = tuple(dict.fromkeys((story, *DEFAULT_PLAYER_METRICS)))
        return build_player_card(row, keys=keys, headline_key=explicit_story or "score")
    if kind == "metric":
        rank, total = rank_of(table, row, story)
        return build_metric_card(row, story, rank=rank, total=total, title=title)
    if kind == "comparison":
        other = find_player(table, opponent_id)
        if other is None:
            ranked = _ranked(table, story, country=country)
            other = next((candidate for candidate in ranked if candidate.get("id") != row.get("id")), None)
        if other is None:
            raise ValueError("Need two players to compare.")
        return build_comparison_card(row, other, keys=(story, *_CONTEXT_METRICS[:4]))
    raise ValueError(f"Unknown card kind {kind!r}.")
