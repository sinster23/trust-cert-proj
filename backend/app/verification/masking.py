from __future__ import annotations

MASK = "******"
MIN_LENGTH_FOR_SUFFIX = 8
VISIBLE_SUFFIX_LENGTH = 4


def mask_student_id(student_id: object) -> str:
    """>= 8 chars: six asterisks + last 4 (punctuation kept). Otherwise six asterisks."""
    if not isinstance(student_id, str) or len(student_id) < MIN_LENGTH_FOR_SUFFIX:
        return MASK
    return MASK + student_id[-VISIBLE_SUFFIX_LENGTH:]