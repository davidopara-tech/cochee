"""Combines Form, Fixtures, and Value advisors into one score."""

from app.advisors.fixtures import get_fixture_scores
from app.advisors.form import get_form_scores
from app.advisors.value import get_value_scores

DEFAULT_WEIGHTS = {
    "form": 1 / 3,
    "fixtures": 1 / 3,
    "value": 1 / 3,
}


def get_combined_scores(db, weights: dict[str, float] | None = None) -> dict[int, dict]:
    """
    Returns {player_id: {'total': float, 'form': float, 'fixtures': float, 'value': float}}
    where 'total' is the weighted average (0-10) and the rest are the raw component scores.
    """
    weights = weights or DEFAULT_WEIGHTS
    total_weight = sum(weights.values())

    form = get_form_scores(db)
    fixtures = get_fixture_scores(db)
    value = get_value_scores(db)

    result = {}
    for pid in form:
        components = {
            "form": form[pid],
            "fixtures": fixtures[pid],
            "value": value[pid],
        }
        total = sum(components[k] * weights[k] for k in weights) / total_weight
        result[pid] = {"total": round(total, 2), **components}
    return result