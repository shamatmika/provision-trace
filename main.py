from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from ecl_engine import ECLValidationError, calculate_portfolio_ecl


app = FastAPI(
    title="Provision Trace Lab ECL API",
    version="0.1.0",
    description=(
        "Development-only illustrative ECL API. Outputs are not approved for IFRS 9 "
        "financial reporting."
    ),
)


frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
allowed_origins = [frontend_origin] if frontend_origin else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


class FacilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facility_id: str = Field(min_length=1, max_length=128)
    stage: int = Field(ge=1, le=3)
    exposure: float = Field(ge=0)
    pd: float = Field(ge=0, le=100, description="Percentage, e.g. 1.2 means 1.2%")
    lgd: float = Field(ge=0, le=100, description="Percentage, e.g. 35 means 35%")
    horizon_years: float = Field(default=1, gt=0)
    discount_rate: float = Field(default=0, gt=-100, description="Annual percentage")
    scenario: str = "base"


class ScenarioInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    weight: float = Field(ge=0, le=1)
    pd_multiplier: float = Field(default=1, ge=0)
    lgd_multiplier: float = Field(default=1, ge=0)
    exposure_multiplier: float = Field(default=1, ge=0)


class CalculationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facilities: list[FacilityInput] = Field(min_length=1, max_length=10000)
    scenarios: list[ScenarioInput] | None = None


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "Provision Trace Lab ECL API",
        "status": "running",
        "model_status": "development_only",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_status": "development_only"}


@app.post("/calculate")
def calculate(request: CalculationRequest) -> dict[str, Any]:
    try:
        records = [item.model_dump() for item in request.facilities]
        scenarios = (
            [item.model_dump() for item in request.scenarios]
            if request.scenarios is not None
            else None
        )
        return calculate_portfolio_ecl(records, scenarios)
    except ECLValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        # Avoid returning internal exception details to API callers.
        raise HTTPException(
            status_code=500,
            detail="Unexpected calculation error. Check server logs.",
        ) from exc
