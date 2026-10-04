from pathlib import Path

import httpx

BASE_URL = "https://friidrett.bul-tromso.no/next/p/"

# Local slug (keys parse_website._PAGE_CONFIG) -> page path on the club site
PAGES = {
    "klubbrekorder-menn-senior": "98928/menn-senior",
    "klubbrekorder-kvinner-senior": "98924/kvinner-senior",
    "klubbrekorder-menn-junior-u23": "98929/menn-u23",
    "klubbrekorder-kvinner-junior-u23": "98926/kvinner-u23",
    "klubbrekorder-menn-junior-u20": "98930/menn-u20",
    "klubbrekorder-kvinner-junior-u20": "98925/kvinner-u20",
    "klubbrekorder-gutter": "98931/gutter",
    "klubbrekorder-jenter": "98927/jenter",
    "klubbrekorder-menn-short-track-innendørs": "98933/short-track-(innendoers)-menn",
    "klubbrekorder-kvinner-short-track-innendørs": "98932/short-track-(innendoers)-kvinner",
}


def scrape_all(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        for slug, path in PAGES.items():
            url = BASE_URL + path
            print(f"Downloading {slug}...")
            resp = client.get(url)
            resp.raise_for_status()
            out = data_dir / f"{slug}.html"
            out.write_text(resp.text, encoding="utf-8")
            print(f"  -> {out}")
    print(f"Done. {len(PAGES)} pages saved to {data_dir}")
