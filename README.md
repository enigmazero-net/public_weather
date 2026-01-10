# public_weather

Fetches the daily Public Weather forecast from https://meteo.gov.lk and stores it as JSON.

## Output files
- `data/meteo_forecast_latest.json` (all available languages)
- `data/meteo_forecast_en_latest.json` (English only)

## Run locally
```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
python scripts/fetch_meteo_en.py
```

## Verify with curl
Local file:
```bash
curl -s file://$(pwd)/data/meteo_forecast_latest.json
```

GitHub raw (replace USER/REPO and branch):
```bash
curl -s https://raw.githubusercontent.com/USER/REPO/main/data/meteo_forecast_latest.json
```
