# Provision Trace Lab: Python ECL API scaffold
## Status
Development scaffold only. The calculation formula is a simplified proxy and is **not**
approved or validated for IFRS 9 financial reporting.
## Files
- `ecl_engine.py`: input validation and simplified scenario-weighted calculation.
- `test_ecl_engine.py`: unit tests.
- `main.py`: FastAPI HTTP API.
- `requirements.txt`: Python dependencies.
- `render.yaml`: Render deployment configuration.

## Input conventions
The API uses one normalized schema:
- `facility_id`: unique facility identifier
- `stage`: integer 1, 2, or 3
- `exposure`: exposure amount in a single, unspecified currency
- `pd`: probability of default as a percentage (1.2 means 1.2%)
- `lgd`: loss given default as a percentage (35 means 35%)
- `horizon_years`: lifetime horizon for Stage 2/3; Stage 1 is forced to one year
- `discount_rate`: annual percentage, e.g. 8 means 8%

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\\Scripts\\activate       # Windows PowerShell
pip install -r requirements.txt
python -m unittest -v
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` to try the API.

## Test request

```json
{
  "facilities": [
    {
      "facility_id": "DEMO-001",
      "stage": 1,
      "exposure": 42000000,
      "pd": 1.2,
      "lgd": 35,
      "horizon_years": 1,
      "discount_rate": 8
    },
    {
      "facility_id": "DEMO-002",
      "stage": 2,
      "exposure": 38000000,
      "pd": 5.8,
      "lgd": 42,
      "horizon_years": 4,
      "discount_rate": 9
    }
  ]
}
```

Free services may sleep when idle and have usage limits. Check the provider's current terms before relying on it.

This scaffold does not implement a complete IFRS 9 method. Make sure to specify and validate at least:

- contractual cash flows, EAD profile, expected recoveries and timing of cash shortfalls;
- approved effective interest rate (or applicable credit-adjusted EIR) discounting;
- 12-month versus lifetime ECL methodology, including term structures/marginal PDs;
- appropriate treatment for credit-impaired Stage 3 exposures;
- forward-looking, probability-weighted macroeconomic scenarios and documented calibration;
- SICR/staging policy, model validation, back-testing, governance and audit trail;
- authentication, authorization, privacy, retention, rate limiting, monitoring and security review.

