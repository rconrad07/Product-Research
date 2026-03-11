# Evals — Gold Standard

This directory contains the ground-truth datasets used to **calibrate** and **validate** the Arbiter judges.

## Structure

```
Gold_Standard/
├── pass/         # Samples that every judge MUST rate as "Pass"
└── fail/         # Samples with known injected errors that judges MUST catch
```

## How to Use

Run the calibration script to measure TPR and TNR:

```powershell
python -m src.scripts.run_calibration
```

The script will compare each judge's decision against the expected outcome in the sample files and print a calibration report.

## Adding New Samples

1. Place the JSON sample in either `pass/` or `fail/`.
2. Add a `_meta` key to the root of the JSON with:
   - `expected_outcome`: `"pass"` or `"fail"`
   - `expected_judge`: which judge(s) should trigger (for `fail` samples)
   - `injected_error`: a human-readable description of what was intentionally broken

See existing samples for reference.
