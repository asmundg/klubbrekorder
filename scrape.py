from pathlib import Path

import httpx

BASE_URL = "https://bul-tromso.no/bul-tromsø/friidrett/"

PAGES = [
    "klubbrekorder-menn-senior",
    "klubbrekorder-kvinner-senior",
    "klubbrekorder-menn-junior-u23",
    "klubbrekorder-kvinner-junior-u23",
    "klubbrekorder-menn-junior-u20",
    "klubbrekorder-kvinner-junior-u20",
    "klubbrekorder-gutter",
    "klubbrekorder-jenter",
    "klubbrekorder-menn-short-track-innendørs",
    "klubbrekorder-kvinner-short-track-innendørs",
]


def scrape_all(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for slug in PAGES:
            url = BASE_URL + slug
            print(f"Downloading {slug}...")
            resp = client.get(url)
            resp.raise_for_status()
            out = data_dir / f"{slug}.html"
            out.write_text(resp.text, encoding="utf-8")
            print(f"  -> {out}")
    print(f"Done. {len(PAGES)} pages saved to {data_dir}")
