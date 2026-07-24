"""Retired unsafe gram seed command.

The historical implementation cleared every serving value before applying a
small keyword map. Use ``rebuild_dish_servings.py`` instead; it records source
and confidence for every generated estimate.
"""


def main() -> None:
    """Explain the safe replacement without modifying the database."""
    print(
        "seed_grams_v2.py is retired. Run "
        "python scripts/rebuild_dish_servings.py --apply instead."
    )


if __name__ == "__main__":
    main()
