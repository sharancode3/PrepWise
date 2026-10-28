from typing import Any, Literal


def normalize_choice(choice: str) -> str:
    """Normalize choice key for deterministic comparison."""
    return choice.strip().lower()


def validate_selected_option(selected: str, valid_options: dict[str, Any] | list[str]) -> bool:
    """Ensure selected option is one of the valid options for the question."""
    normalized_selected = normalize_choice(selected)
    keys = valid_options.keys() if isinstance(valid_options, dict) else valid_options
    normalized_keys = {normalize_choice(k) for k in keys}
    return normalized_selected in normalized_keys


def score_single_choice(selected_option: str, answer_option: str) -> bool:
    """Deterministic server-side scoring for single-choice questions."""
    return normalize_choice(selected_option) == normalize_choice(answer_option)


def classify_evidence(hints_used: int, prior_attempt_count: int) -> tuple[int, Literal["independent", "supported"]]:
    """
    Classify attempt as independent or supported.
    An attempt is independent ONLY if:
    1. It is the student's first accepted attempt on that question (prior_attempt_count == 0).
    2. hints_used == 0.
    """
    if hints_used == 0 and prior_attempt_count == 0:
        return 1, "independent"
    return 0, "supported"


def compute_skill_evidence(skill_id: str, attempts: list[dict[str, Any]], window_size: int = 8) -> dict[str, Any]:
    """
    Compute rolling per-skill evidence estimate and counts.
    Uses up to last `window_size` (W=8) eligible independent items.
    Policy v1:
    - n == 0: evidence_status = "unknown", performance_estimate = None
    - n < 3: evidence_status = "limited"
    - n >= 3 and estimate <= 0.40: evidence_status = "needs_attention"
    - n >= 4 and estimate >= 0.80: evidence_status = "strong"
    - otherwise: evidence_status = "ordinary"
    """
    independent_attempts = [a for a in attempts if a.get("is_independent_evidence") == 1]
    supported_attempts = [a for a in attempts if a.get("is_independent_evidence") == 0]

    independent_count = len(independent_attempts)
    supported_count = len(supported_attempts)

    # Sort independent attempts chronologically
    independent_attempts.sort(key=lambda a: (a.get("submitted_at") or "", a.get("id") or ""))

    # Take the rolling window of the most recent eligible attempts
    window = independent_attempts[-window_size:] if len(independent_attempts) > window_size else independent_attempts
    n = len(window)

    if n == 0:
        return {
            "skill_id": skill_id,
            "independent_count": independent_count,
            "supported_count": supported_count,
            "performance_estimate": None,
            "evidence_status": "unknown",
            "attempt_ids": [],
        }

    c = sum(1 for a in window if int(a.get("correct", 0)) == 1)
    w = n - c
    alpha = 1.0 + c
    beta = 1.0 + w
    estimate = round(alpha / (alpha + beta), 4)

    if n < 3:
        evidence_status = "limited"
    elif estimate <= 0.40:
        evidence_status = "needs_attention"
    elif n >= 4 and estimate >= 0.80:
        evidence_status = "strong"
    else:
        evidence_status = "ordinary"

    attempt_ids = [a["id"] for a in window if "id" in a]

    return {
        "skill_id": skill_id,
        "independent_count": independent_count,
        "supported_count": supported_count,
        "performance_estimate": estimate,
        "evidence_status": evidence_status,
        "attempt_ids": attempt_ids,
    }
