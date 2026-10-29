from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable
import math


class ECLValidationError(ValueError):
    pass

@dataclass(frozen=True)
class Facility:
    facility_id: str
    stage: int
    exposure: float
    pd: float                  # percentage: 0–100
    lgd: float                 # percentage: 0–100
    horizon_years: float       # Stage 1 is forced to 1 year in this prototype
    discount_rate: float       # annual percentage: e.g. 8 means 8%
    scenario: str = "base"


@dataclass(frozen=True)
class Scenario:
    name: str
    weight: float              # probability weight, 0–1
    pd_multiplier: float = 1.0
    lgd_multiplier: float = 1.0
    exposure_multiplier: float = 1.0


DEFAULT_SCENARIOS = (
    Scenario("upside", 0.20, pd_multiplier=0.80, lgd_multiplier=0.90),
    Scenario("base", 0.60, pd_multiplier=1.00, lgd_multiplier=1.00),
    Scenario("downside", 0.20, pd_multiplier=1.25, lgd_multiplier=1.10),
)


def _finite_number(value: Any, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ECLValidationError(f"Row {row_number}: '{field}' must be numeric.") from None
    if not math.isfinite(number):
        raise ECLValidationError(f"Row {row_number}: '{field}' must be finite.")
    return number


def validate_facilities(records: Iterable[dict[str, Any]]) -> list[Facility]:
    rows = list(records)
    if not rows:
        raise ECLValidationError("At least one facility record is required.")

    facilities: list[Facility] = []
    seen_ids: set[str] = set()

    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ECLValidationError(f"Row {row_number}: each record must be an object.")

        facility_id = str(row.get("facility_id", "")).strip()
        if not facility_id:
            raise ECLValidationError(f"Row {row_number}: 'facility_id' is required.")
        if facility_id in seen_ids:
            raise ECLValidationError(
                f"Row {row_number}: duplicate facility_id '{facility_id}'."
            )
        seen_ids.add(facility_id)

        stage_value = _finite_number(row.get("stage"), "stage", row_number)
        if not stage_value.is_integer() or int(stage_value) not in (1, 2, 3):
            raise ECLValidationError(f"Row {row_number}: stage must be 1, 2, or 3.")
        stage = int(stage_value)

        exposure = _finite_number(row.get("exposure"), "exposure", row_number)
        pd = _finite_number(row.get("pd"), "pd", row_number)
        lgd = _finite_number(row.get("lgd"), "lgd", row_number)
        horizon = _finite_number(row.get("horizon_years", 1), "horizon_years", row_number)
        discount_rate = _finite_number(row.get("discount_rate", 0), "discount_rate", row_number)

        if exposure < 0:
            raise ECLValidationError(f"Row {row_number}: exposure cannot be negative.")
        if not 0 <= pd <= 100:
            raise ECLValidationError(f"Row {row_number}: pd must be between 0 and 100 (%).")
        if not 0 <= lgd <= 100:
            raise ECLValidationError(f"Row {row_number}: lgd must be between 0 and 100 (%).")
        if horizon <= 0:
            raise ECLValidationError(f"Row {row_number}: horizon_years must be greater than 0.")
        if discount_rate <= -100:
            raise ECLValidationError(f"Row {row_number}: discount_rate must be greater than -100 (%).")

        facilities.append(Facility(
            facility_id=facility_id,
            stage=stage,
            exposure=exposure,
            pd=pd,
            lgd=lgd,
            horizon_years=horizon,
            discount_rate=discount_rate,
            scenario=str(row.get("scenario", "base")).strip().lower() or "base",
        ))

    return facilities


def validate_scenarios(scenarios: Iterable[dict[str, Any]] | None = None) -> list[Scenario]:
    if scenarios is None:
        return list(DEFAULT_SCENARIOS)

    raw = list(scenarios)
    if not raw:
        raise ECLValidationError("At least one scenario is required.")

    result: list[Scenario] = []
    names: set[str] = set()
    for i, item in enumerate(raw, start=1):
        name = str(item.get("name", "")).strip().lower()
        if not name:
            raise ECLValidationError(f"Scenario {i}: name is required.")
        if name in names:
            raise ECLValidationError(f"Scenario {i}: duplicate scenario name '{name}'.")
        names.add(name)

        weight = _finite_number(item.get("weight"), "weight", i)
        pd_mult = _finite_number(item.get("pd_multiplier", 1), "pd_multiplier", i)
        lgd_mult = _finite_number(item.get("lgd_multiplier", 1), "lgd_multiplier", i)
        exposure_mult = _finite_number(item.get("exposure_multiplier", 1), "exposure_multiplier", i)

        if not 0 <= weight <= 1:
            raise ECLValidationError(f"Scenario '{name}': weight must be between 0 and 1.")
        if min(pd_mult, lgd_mult, exposure_mult) < 0:
            raise ECLValidationError(f"Scenario '{name}': multipliers cannot be negative.")

        result.append(Scenario(name, weight, pd_mult, lgd_mult, exposure_mult))

    total_weight = sum(s.weight for s in result)
    if not math.isclose(total_weight, 1.0, rel_tol=0, abs_tol=1e-6):
        raise ECLValidationError(
            f"Scenario weights must sum to 1.0; received {total_weight:.6f}."
        )
    return result


def calculate_facility_ecl(facility: Facility, scenarios: list[Scenario]) -> dict[str, Any]:
    horizon = 1.0 if facility.stage == 1 else facility.horizon_years
    scenario_results = []
    weighted_ecl = 0.0

    for scenario in scenarios:
        adjusted_exposure = facility.exposure * scenario.exposure_multiplier
        adjusted_pd = min(100.0, facility.pd * scenario.pd_multiplier)
        adjusted_lgd = min(100.0, facility.lgd * scenario.lgd_multiplier)

        # Prototype only: for lifetime stages, approximate cumulative PD by
        # 1 - (1 - annual PD)^horizon. This assumes a constant annual PD.
        annual_pd_fraction = adjusted_pd / 100.0
        cumulative_pd = annual_pd_fraction if facility.stage == 1 else (
            1.0 - (1.0 - annual_pd_fraction) ** horizon
        )

        undiscounted = adjusted_exposure * cumulative_pd * (adjusted_lgd / 100.0)
        discount_factor = (1.0 + facility.discount_rate / 100.0) ** horizon
        discounted = undiscounted / discount_factor if discount_factor > 0 else 0.0
        contribution = discounted * scenario.weight
        weighted_ecl += contribution

        scenario_results.append({
            "scenario": scenario.name,
            "weight": scenario.weight,
            "adjusted_exposure": round(adjusted_exposure, 6),
            "adjusted_pd_percent": round(adjusted_pd, 6),
            "adjusted_lgd_percent": round(adjusted_lgd, 6),
            "horizon_years_used": horizon,
            "discount_factor": round(discount_factor, 8),
            "undiscounted_ecl_proxy": round(undiscounted, 6),
            "discounted_ecl_proxy": round(discounted, 6),
            "weighted_contribution": round(contribution, 6),
        })

    return {
        "facility_id": facility.facility_id,
        "stage": facility.stage,
        "exposure": facility.exposure,
        "pd_percent": facility.pd,
        "lgd_percent": facility.lgd,
        "horizon_years_used": horizon,
        "illustrative_ecl": round(weighted_ecl, 6),
        "illustrative_ecl_rate_percent": round(
            (weighted_ecl / facility.exposure * 100.0) if facility.exposure else 0.0, 6
        ),
        "scenario_results": scenario_results,
        "methodology_label": "SIMPLIFIED_DEVELOPMENT_PROXY_NOT_IFRS9_PRODUCTION",
    }


def calculate_portfolio_ecl(
    records: Iterable[dict[str, Any]],
    scenarios: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    facilities = validate_facilities(records)
    scenario_set = validate_scenarios(scenarios)
    results = [calculate_facility_ecl(f, scenario_set) for f in facilities]

    total_exposure = sum(f.exposure for f in facilities)
    total_ecl = sum(r["illustrative_ecl"] for r in results)
    stage_summary = {}
    for stage in (1, 2, 3):
        stage_facilities = [f for f in facilities if f.stage == stage]
        stage_ecl = sum(r["illustrative_ecl"] for r in results if r["stage"] == stage)
        stage_summary[str(stage)] = {
            "facility_count": len(stage_facilities),
            "exposure": round(sum(f.exposure for f in stage_facilities), 6),
            "illustrative_ecl": round(stage_ecl, 6),
        }

    return {
        "status": "success",
        "model_status": "development_only",
        "methodology_warning": (
            "Illustrative development proxy only. Not validated for IFRS 9 financial "
            "reporting or real customer decisions."
        ),
        "currency": "not_specified",
        "facility_count": len(facilities),
        "total_exposure": round(total_exposure, 6),
        "total_illustrative_ecl": round(total_ecl, 6),
        "portfolio_ecl_rate_percent": round(
            (total_ecl / total_exposure * 100.0) if total_exposure else 0.0, 6
        ),
        "scenario_weights": {s.name: s.weight for s in scenario_set},
        "stage_summary": stage_summary,
        "facilities": results,
    }


def facility_to_dict(facility: Facility) -> dict[str, Any]:
    return asdict(facility)
