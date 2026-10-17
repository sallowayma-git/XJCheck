"""Small, dependency-free catalog of the user-facing issue rule families."""

USER_VISIBLE_RULE_IDS = frozenset(
    {
        "R-SUPERWORKS-CONFLICT",
        "R-TABLE-MAPPING-SOURCE-CONFLICT",
        "R-CROSS-PAGE-CONFLICT",
        "R-MANY-TO-ONE",
        "R-PAIR-MISSING-SIDE",
        "R-PAIR-LOW-CONFIDENCE",
    }
)
