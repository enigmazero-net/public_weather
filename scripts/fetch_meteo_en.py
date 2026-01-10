import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Callable, Dict

from playwright.sync_api import sync_playwright

URL = "https://meteo.gov.lk/"  # homepage shows the daily forecast (loaded dynamically)
MIN_FETCH_INTERVAL = timedelta(hours=3)

LANG_MARKERS = {
    "si": re.compile(r"\d{4}.*කාලගුණ අනාවැකිය"),
    "en": re.compile(r"WEATHER FORECAST FOR"),
    "ta": re.compile(r"\d{4}.*வானிலை முன்னறிவிப்பு"),
}


def normalize_ws(s: str) -> str:
    s = s.replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def split_blocks(full_text: str) -> Dict[str, str]:
    indices = []
    for lang, pattern in LANG_MARKERS.items():
        match = pattern.search(full_text)
        if match:
            indices.append((match.start(), lang))

    if not indices:
        raise RuntimeError("Could not find any forecast blocks in page text")

    indices.sort()
    blocks = {}
    for idx, (start, lang) in enumerate(indices):
        end = indices[idx + 1][0] if idx + 1 < len(indices) else None
        blocks[lang] = full_text[start:end].strip()

    return blocks


def parse_block(block_text: str, is_issued: Callable[[str], bool]) -> dict:
    block_text = normalize_ws(block_text)
    lines = [ln.strip() for ln in block_text.split("\n") if ln.strip()]

    title = lines[0] if lines else ""
    issued = ""
    body_lines = []

    for ln in lines[1:]:
        if not issued and is_issued(ln):
            issued = ln
        else:
            body_lines.append(ln)

    return {"title": title, "issued": issued, "body": "\n\n".join(body_lines).strip()}


def should_fetch(latest_path: str, now: datetime) -> bool:
    try:
        with open(latest_path, "r", encoding="utf-8") as f:
            previous = json.load(f)
    except FileNotFoundError:
        return True
    except json.JSONDecodeError:
        return True

    fetched_at = previous.get("fetched_at", "")
    if not fetched_at:
        return True

    try:
        last = datetime.fromisoformat(fetched_at)
    except ValueError:
        return True

    if last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)

    return (now - last) >= MIN_FETCH_INTERVAL


def main():
    sl_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(sl_tz)
    latest_path = "data/meteo_forecast_latest.json"

    if not should_fetch(latest_path, now):
        print("Skipping fetch: last update was under 3 hours ago.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(URL, wait_until="networkidle", timeout=120000)

        page.wait_for_timeout(2000)
        page.wait_for_selector("text=WEATHER FORECAST FOR", timeout=120000)

        text = page.inner_text("body")
        browser.close()

    blocks = split_blocks(text)
    if "en" not in blocks:
        raise RuntimeError("Could not find English forecast block")

    parsed = {}
    if "si" in blocks:
        parsed["si"] = parse_block(blocks["si"], lambda ln: "නිකුත්" in ln)
    if "en" in blocks:
        parsed["en"] = parse_block(blocks["en"], lambda ln: ln.lower().startswith("issued at"))
    if "ta" in blocks:
        parsed["ta"] = parse_block(blocks["ta"], lambda ln: "வெளியிட" in ln)

    fetched_at = now.isoformat()

    out_all = {
        "source": "meteo.gov.lk",
        "lang": "multi",
        "fetched_at": fetched_at,
        **parsed,
    }

    os.makedirs("data", exist_ok=True)

    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(out_all, f, ensure_ascii=False, indent=2)

    out_en = {
        "source": "meteo.gov.lk",
        "lang": "en",
        "fetched_at": fetched_at,
        **parsed["en"],
    }

    with open("data/meteo_forecast_en_latest.json", "w", encoding="utf-8") as f:
        json.dump(out_en, f, ensure_ascii=False, indent=2)

    print("Wrote data/meteo_forecast_latest.json")
    print("Wrote data/meteo_forecast_en_latest.json")

if __name__ == "__main__":
    main()
