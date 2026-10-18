"""The metric catalogue.

Every number a card or caption shows goes through `format_metric`, so a value
can never appear on a share image with the wrong unit or the wrong number of
decimals. `direction` matters: for defensive rating and turnover percentage a
lower number is the better one, and the card builder highlights accordingly.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    label: str
    short: str
    digits: int = 2
    direction: int = 1  # 1 = higher is better, -1 = lower is better
    percent: bool = False
    #: The API stores some percentages as 0-1 fractions and others as 0-100.
    fraction: bool = False
    description: str = ""


METRICS: dict[str, Metric] = {
    # Catch & Stats own ratings
    "score": Metric("Catch & Stats rating", "RTG", 2, 1),
    "custom_efficiency_rating": Metric("Custom efficiency rating", "EFF", 2, 1),
    "per": Metric("Player efficiency rating", "PER", 2, 1),
    "valuation": Metric("Valuation", "VAL", 2, 1),
    "net_rating": Metric("Net rating", "NET", 2, 1),
    "offensive_rating": Metric("Offensive rating", "ORtg", 2, 1),
    "defensive_rating": Metric("Defensive rating", "DRtg", 2, -1),
    "minus_plus": Metric("Plus / minus", "+/-", 2, 1),
    # Shooting
    "ts_pct": Metric("True shooting", "TS%", 1, 1, percent=True, fraction=True),
    "efg_pct": Metric("Effective field goal", "eFG%", 1, 1, percent=True, fraction=True),
    "pps": Metric("Points per shot", "PPS", 3, 1),
    "field_goals_two_percent": Metric("Two-point shooting", "2P%", 1, 1),
    "field_goals_three_percent": Metric("Three-point shooting", "3P%", 1, 1),
    "free_throws_percent": Metric("Free-throw shooting", "FT%", 1, 1),
    "three_p_rate": Metric("Three-point rate", "3PAr", 1, 1, percent=True, fraction=True),
    "free_throw_rate": Metric("Free-throw rate", "FTr", 1, 1, percent=True, fraction=True),
    # Playmaking / possession
    "usage_pct": Metric("Usage", "USG%", 1, 1, percent=True),
    "ast_pct": Metric("Assist percentage", "AST%", 1, 1, percent=True),
    "ast_to_ratio": Metric("Assist-to-turnover", "A/TO", 2, 1),
    "ast_ratio": Metric("Assist ratio", "AST ratio", 2, 1),
    "tov_pct": Metric("Turnover percentage", "TOV%", 1, -1, percent=True, fraction=True),
    "oreb_pct": Metric("Offensive rebound percentage", "OREB%", 1, 1, percent=True),
    "drb_pct": Metric("Defensive rebound percentage", "DREB%", 1, 1, percent=True),
    "trb_pct": Metric("Total rebound percentage", "REB%", 1, 1, percent=True),
    "stocks": Metric("Stocks (steals + blocks)", "STOCKS", 2, 1),
    # Consistency: the part nobody else publishes
    "consistency_score": Metric("Consistency score", "CONS", 1, 1),
    "cv": Metric("Coefficient of variation", "CV", 2, -1),
    "fantasy_consistency_score": Metric("Fantasy consistency", "F-CONS", 1, 1),
    "fantasy_points_floor": Metric("Fantasy floor", "FLOOR", 2, 1),
    "fantasy_points_ceiling": Metric("Fantasy ceiling", "CEIL", 2, 1),
    "home_court_advantage": Metric("Home-court advantage", "HCA", 2, 1),
    "beta_against_win": Metric("Performance in wins (beta)", "β W", 2, 1),
    "beta_against_loss": Metric("Performance in losses (beta)", "β L", 2, -1),
    "std": Metric("Game-to-game swing", "STD", 2, -1),
    "r_squared": Metric("Model fit (R²)", "R²", 3, 1),
    # Team level (team-season rows are flat, not nested under "metrics")
    "avg_pace": Metric("Pace", "PACE", 1, 1),
    "avg_possessions": Metric("Possessions per game", "POSS", 1, 1),
    "team_average_fantasy_points": Metric("Average fantasy points", "FP", 2, 1),
    "allowed_team_average_fantasy_points": Metric("Fantasy points allowed", "FP allowed", 2, -1),
    # Box score basics
    "total_rebounds": Metric("Rebounds per game", "REB", 2, 1),
    "assistances": Metric("Assists per game", "AST", 2, 1),
    "steal": Metric("Steals per game", "STL", 2, 1),
    "turnovers": Metric("Turnovers per game", "TO", 2, -1),
    "blocks_favour": Metric("Blocks per game", "BLK", 2, 1),
    "time_played": Metric("Minutes per game", "MIN", 1, 1),
    "age": Metric("Age", "AGE", 0, 1),
}

#: Metrics worth building a whole post around: narrative, proprietary, or both.
STORY_METRICS = (
    "home_court_advantage",
    "consistency_score",
    "fantasy_consistency_score",
    "fantasy_points_ceiling",
    "ts_pct",
    "ast_to_ratio",
    "usage_pct",
)

#: Used when a card needs a quick "what else" set.
DEFAULT_PLAYER_METRICS = ("score", "ts_pct", "usage_pct", "per", "ast_to_ratio")

#: Used for team matchups.
TEAM_METRICS = (
    "offensive_rating",
    "defensive_rating",
    "avg_pace",
    "team_average_fantasy_points",
)


def as_float(value) -> float | None:
    """The API mixes numbers with numeric strings ("51.28", "24.39"). Normalise."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


#: Ranges outside which a number is a data-entry artefact, not a stat.
#: A 2-minute cameo can produce a 150% true-shooting night; it should never
#: become a leaderboard card.
PLAUSIBLE: dict[str, tuple[float, float]] = {
    "ts_pct": (0.0, 0.85),
    "efg_pct": (0.0, 0.85),
    "three_p_rate": (0.0, 1.0),
    "free_throw_rate": (0.0, 1.0),
    "tov_pct": (0.0, 0.6),
    "usage_pct": (0.0, 60.0),
    "ast_pct": (0.0, 60.0),
    "oreb_pct": (0.0, 40.0),
    "drb_pct": (0.0, 50.0),
    "trb_pct": (0.0, 40.0),
    "net_rating": (-40.0, 40.0),
    "offensive_rating": (40.0, 200.0),
    "defensive_rating": (40.0, 200.0),
    "per": (-20.0, 60.0),
    "consistency_score": (1.0, 100.0),
    "fantasy_consistency_score": (1.0, 100.0),
    "ast_to_ratio": (0.0, 20.0),
    "cv": (0.0, 3.0),
}


def is_plausible(key: str, value) -> bool:
    number = as_float(value)
    if number is None:
        return False
    bounds = PLAUSIBLE.get(key)
    return True if bounds is None else bounds[0] <= number <= bounds[1]


def format_metric(key: str, value) -> str:
    number = as_float(value)
    metric = METRICS.get(key)
    if number is None:
        return "—"
    if key in PLAUSIBLE and not is_plausible(key, number):
        # A number outside the possible range is a data artefact. Showing a
        # dash is honest; showing "106.3%" would cost more trust than it buys.
        return "—"
    if key.endswith("_percent") and not metric:
        return f"{number:.1f}%"
    if metric is None:
        return f"{number:.2f}"
    if metric.percent:
        scaled = number * 100 if metric.fraction else number
        return f"{scaled:.{metric.digits}f}%"
    return f"{number:.{metric.digits}f}"


#: Greek labels for the metrics that show up on cards and captions. The site's
#: UI is English + Greek, so Greek drafts translate the labels too; anything
#: missing here falls back to the English label rather than a guess.
GREEK_LABELS = {
    "score": "Αξιολόγηση",
    "ts_pct": "Αληθής ευστοχία",
    "efg_pct": "Ενεργή ευστοχία",
    "usage_pct": "Χρήση κατοχών",
    "per": "Δείκτης απόδοσης",
    "ast_to_ratio": "Ασίστ/λάθη",
    "net_rating": "Καθαρή αξιολόγηση",
    "offensive_rating": "Επιθετική αξιολόγηση",
    "defensive_rating": "Αμυντική αξιολόγηση",
    "home_court_advantage": "Πλεονέκτημα έδρας",
    "consistency_score": "Σταθερότητα",
    "fantasy_consistency_score": "Σταθερότητα fantasy",
    "fantasy_points_ceiling": "Οροφή fantasy",
    "fantasy_points_floor": "Βάση fantasy",
    "avg_pace": "Ρυθμός",
    "team_average_fantasy_points": "Μέσοι πόντοι fantasy",
    "allowed_team_average_fantasy_points": "Πόντοι fantasy που δέχεται",
    "total_rebounds": "Ριμπάουντ ανά αγώνα",
    "assistances": "Ασίστ ανά αγώνα",
    "turnovers": "Λάθη ανά αγώνα",
    "steal": "Κλεψίματα ανά αγώνα",
    "blocks_favour": "Τάπες ανά αγώνα",
    "time_played": "Λεπτά ανά αγώνα",
}


def metric_label(key: str, locale: str = "en") -> str:
    """Human label. Greek falls back to English for the long tail of metrics."""
    if locale == "el":
        greek = GREEK_LABELS.get(key)
        if greek:
            return greek
    metric = METRICS.get(key)
    return metric.label if metric else key.replace("_", " ").capitalize()


def metric_short(key: str) -> str:
    metric = METRICS.get(key)
    return metric.short if metric else key[:8].upper()


def is_better(key: str, candidate, current) -> bool:
    """True when `candidate` beats `current` for this metric's direction."""
    a, b = as_float(candidate), as_float(current)
    if a is None or b is None:
        return False
    metric = METRICS.get(key)
    return a > b if (metric is None or metric.direction == 1) else a < b
