"""Retired migration entry point for the removed conversion-rate subsystem.

The current dish-level architecture stores ``VnDish`` and ``VnIngredient``
records only. Volume conversion tables belonged to the removed user-recipe flow.
"""


def main() -> None:
    """Explain why this legacy seed step is no longer applicable."""
    raise SystemExit(
        "seed_conversion_rates.py is retired: the current schema has no "
        "conversion_rates table."
    )


if __name__ == "__main__":
    main()
