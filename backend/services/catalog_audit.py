"""Read-only audit rules and report rendering for the nutrition catalog."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping

from backend.services.catalog_quality import (
    DISH_NUTRIENT_FIELDS,
    ENERGY_MISMATCH_RATIO,
    INGREDIENT_NUTRIENT_FIELDS,
    _dish_physical_codes,
    _energy_mismatch,
    _number,
    _record_id,
    _record_name,
    accent_insensitive_name_key,
    canonical_name_key,
)


def _issue(
    *,
    code: str,
    severity: str,
    entity_type: str,
    record_id: str,
    name: str,
    message: str,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "code": code,
        "severity": severity,
        "entity_type": entity_type,
        "record_id": record_id,
        "name": name,
        "message": message,
        "details": dict(details or {}),
    }


def _audit_nutrients(
    record: Mapping[str, object], entity_type: str, fields: Iterable[str]
) -> list[dict[str, object]]:
    negative = {field: _number(record, field) for field in fields if _number(record, field) < 0}
    if not negative:
        return []
    return [
        _issue(
            code="negative_nutrient",
            severity="error",
            entity_type=entity_type,
            record_id=_record_id(record),
            name=_record_name(record, entity_type),
            message="Nutrient values must not be negative.",
            details={"fields": negative},
        )
    ]


def _audit_ingredient(record: Mapping[str, object]) -> list[dict[str, object]]:
    issues = _audit_nutrients(record, "ingredient", INGREDIENT_NUTRIENT_FIELDS)
    mismatch = _energy_mismatch(record, "ingredient")
    if _number(record, "calories_per_g") > 0 and mismatch > ENERGY_MISMATCH_RATIO:
        issues.append(_issue(
            code="energy_macro_mismatch",
            severity="warning",
            entity_type="ingredient",
            record_id=_record_id(record),
            name=_record_name(record, "ingredient"),
            message="Calories differ materially from the Atwater macro estimate.",
            details={"relative_difference": round(mismatch, 4)},
        ))
    return issues


def _audit_dish(record: Mapping[str, object]) -> list[dict[str, object]]:
    issues = _audit_nutrients(record, "dish", DISH_NUTRIENT_FIELDS)
    name = _record_name(record, "dish")
    record_id = _record_id(record)
    grams = _number(record, "typical_grams")
    if grams <= 0:
        conflict = record.get("typical_grams_source") == "nutrition_conflict"
        issues.append(_issue(
            code=(
                "unresolved_nutrition_conflict" if conflict else "missing_serving_weight"
            ),
            severity="warning",
            entity_type="dish",
            record_id=record_id,
            name=name,
            message=(
                "Source calories and macros conflict; serving weight requires review."
                if conflict
                else "Serving totals cannot be scaled until a measured weight is available."
            ),
        ))
    for code in _dish_physical_codes(record):
        message = (
            "Energy density exceeds the physical food limit."
            if code == "implausible_energy_density"
            else "Macro mass is too large for the estimated serving weight."
        )
        issues.append(_issue(
            code=code,
            severity="error",
            entity_type="dish",
            record_id=record_id,
            name=name,
            message=message,
            details={"typical_grams": grams},
        ))
    mismatch = _energy_mismatch(record, "dish")
    if _number(record, "total_calories") > 0 and mismatch > ENERGY_MISMATCH_RATIO:
        issues.append(_issue(
            code="energy_macro_mismatch",
            severity="warning",
            entity_type="dish",
            record_id=record_id,
            name=name,
            message="Calories differ materially from the Atwater macro estimate.",
            details={"relative_difference": round(mismatch, 4)},
        ))
    return issues


def _audit_candidate(record: Mapping[str, object]) -> list[dict[str, object]]:
    if record.get("status") != "pending":
        return []
    if _number(record, "typical_grams") > 0 and _number(record, "total_calories") > 0:
        return []
    return [_issue(
        code="unapprovable_candidate",
        severity="error",
        entity_type="candidate",
        record_id=_record_id(record),
        name=_record_name(record, "candidate"),
        message="Pending candidate lacks positive calories or serving weight.",
    )]


def _case_duplicate_issues(
    records: list[Mapping[str, object]], entity_type: str
) -> list[dict[str, object]]:
    groups: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        source = str(record.get("source", "")) if entity_type == "ingredient" else ""
        groups[(source, canonical_name_key(_record_name(record, entity_type)))].append(record)
    issues: list[dict[str, object]] = []
    for group in groups.values():
        if len(group) > 1:
            issues.append(_issue(
                code="case_duplicate",
                severity="error",
                entity_type=entity_type,
                record_id=",".join(sorted(_record_id(record) for record in group)),
                name=" | ".join(sorted({_record_name(record, entity_type) for record in group})),
                message="Records differ only by case or whitespace within the same catalog source.",
                details={"copies": len(group)},
            ))
    return issues


def _accent_collision_issues(
    records: list[Mapping[str, object]], entity_type: str
) -> list[dict[str, object]]:
    groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        groups[accent_insensitive_name_key(_record_name(record, entity_type))].append(record)
    issues: list[dict[str, object]] = []
    for group in groups.values():
        canonical_keys = {canonical_name_key(_record_name(row, entity_type)) for row in group}
        if len(canonical_keys) > 1:
            issues.append(_issue(
                code="accent_insensitive_collision",
                severity="warning",
                entity_type=entity_type,
                record_id=",".join(sorted(_record_id(record) for record in group)),
                name=" | ".join(sorted({_record_name(record, entity_type) for record in group})),
                message="Accent-insensitive search collapses distinct canonical names; do not auto-merge.",
                details={"copies": len(group)},
            ))
    return issues


def audit_catalog_records(
    *,
    ingredients: list[Mapping[str, object]],
    dishes: list[Mapping[str, object]],
    candidates: list[Mapping[str, object]],
) -> dict[str, object]:
    """Return a deterministic, JSON-serializable audit report."""
    issues = [
        *(issue for record in ingredients for issue in _audit_ingredient(record)),
        *(issue for record in dishes for issue in _audit_dish(record)),
        *(issue for record in candidates for issue in _audit_candidate(record)),
        *_case_duplicate_issues(ingredients, "ingredient"),
        *_case_duplicate_issues(dishes, "dish"),
        *_accent_collision_issues(dishes, "dish"),
    ]
    severity_order = {"error": 0, "warning": 1}
    issues.sort(key=lambda issue: (
        severity_order.get(str(issue["severity"]), 9),
        str(issue["code"]),
        str(issue["entity_type"]),
        str(issue["name"]),
    ))
    severity_counts = Counter(str(issue["severity"]) for issue in issues)
    code_counts = Counter(str(issue["code"]) for issue in issues)
    return {
        "summary": {
            "ingredients": len(ingredients),
            "dishes": len(dishes),
            "candidates": len(candidates),
            "errors": severity_counts["error"],
            "warnings": severity_counts["warning"],
            "issues_by_code": dict(sorted(code_counts.items())),
        },
        "issues": issues,
    }


def render_markdown_report(report: Mapping[str, object]) -> str:
    """Render an audit report suitable for CI artifacts and human review."""
    summary = report["summary"]
    assert isinstance(summary, Mapping)
    lines = [
        "# FoodAI Catalog Quality Audit",
        "",
        "## Summary",
        "",
        f"- Ingredients: **{summary['ingredients']}**",
        f"- Dishes: **{summary['dishes']}**",
        f"- Candidates: **{summary['candidates']}**",
        f"- Errors: **{summary['errors']}**",
        f"- Warnings: **{summary['warnings']}**",
        "",
        "## Issues",
        "",
        "| Severity | Code | Entity | Name | Message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for issue in report["issues"]:
        assert isinstance(issue, Mapping)
        name = str(issue["name"]).replace("|", "\\|")
        message = str(issue["message"]).replace("|", "\\|")
        lines.append(
            f"| {issue['severity']} | {issue['code']} | "
            f"{issue['entity_type']} | {name} | {message} |"
        )
    return "\n".join(lines) + "\n"
