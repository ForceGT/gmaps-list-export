#!/usr/bin/env python3
"""Export any Google Maps list (shared or joined, short or long URL) to
JSON / CSV / GeoJSON / KML / GPX. No browser, no sign-in, no Google Takeout,
no dependencies outside the standard library.

Usage:
    python3 gmaps_list_export.py "<url>" [--format json,csv,geojson,kml,gpx] [--out places]

Examples:
    python3 gmaps_list_export.py "https://maps.app.goo.gl/XXXXXXXX"
    python3 gmaps_list_export.py "https://www.google.com/maps/@.../data=..." --format kml,csv
"""
import argparse
import csv
import http.cookiejar
import json
import re
import secrets
import sys
import urllib.parse
import urllib.request

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Deliberately NOT the full Chrome UA above: a modern browser UA makes the
# short-link redirector serve a JS interstitial (200, no Location header)
# instead of a plain redirect. A bare "Mozilla/5.0" reliably gets the 302.
SHORTLINK_USER_AGENT = "Mozilla/5.0"


def resolve_list(url):
    """Follow a short (maps.app.goo.gl/...) or long Maps URL to the list's
    id + share token. Works on either form. A long URL resolves to itself."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    req = urllib.request.Request(url, headers={"User-Agent": SHORTLINK_USER_AGENT})
    final_url = opener.open(req).geturl()

    list_id = None
    m = re.search(r"!2s(-?[\w-]+)!", final_url) or re.search(r"/placelists/list/(-?[\w-]+)", final_url)
    if m:
        list_id = m.group(1)

    token = None
    m = re.search(r"token%3D([\w-]+)", final_url) or re.search(r"[?&]token=([\w-]+)", final_url)
    if m:
        token = m.group(1)

    if not list_id:
        raise SystemExit(f"Couldn't find a list id in the resolved URL:\n{final_url}\n"
                          "Make sure the link points at a Maps list (a 'placelists/list/...' URL), not a single place or a plain map view.")

    return list_id, token, opener


def fetch_places(list_id, token, opener):
    """Call the (undocumented) entitylist/getlist endpoint the list's own
    page uses to render itself, and return the raw place entries."""
    list_page_url = f"https://www.google.com/maps/placelists/list/{list_id}"
    if token:
        list_page_url += f"?token={token}"

    # The !1s value is a per-session id the real page generates; a random
    # one works fine, it doesn't appear to be validated server-side.
    session = secrets.token_urlsafe(16)
    pb = (
        "!2e2!3e2!4i500!6m3"
        f"!1s{session}"
        "!15i204459!28e2"
        f"!13s{urllib.parse.quote(list_page_url, safe='')}"
        "!16b1"
    )
    qs = urllib.parse.urlencode({"authuser": "0", "hl": "en", "gl": "in"})
    api_url = f"https://www.google.com/maps/preview/entitylist/getlist?{qs}&pb={pb}"

    req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
    text = opener.open(req).read().decode("utf-8")
    if text.startswith(")]}'"):
        text = text[4:]

    data = json.loads(text)
    list_title = data[0][4] if len(data[0]) > 4 else None
    raw_places = data[0][8]

    # 500 entries per call (the `4i500` param); page through if the list is
    # bigger. Untested against a real >500 list. The list's total count
    # lives at data[0][12] if you want to sanity-check completeness.
    return list_title, raw_places


def parse_place(p):
    info = p[1]
    name = p[2]
    label = info[2] if len(info) > 2 else None
    address = info[4] if len(info) > 4 else None
    latlng = info[5] if len(info) > 5 else None
    lat, lng = (latlng[2], latlng[3]) if latlng and len(latlng) >= 4 else (None, None)
    cid = info[6] if len(info) > 6 else None
    place_id = info[7] if len(info) > 7 else None
    return {
        "name": name,
        "label": label,
        "address": address,
        "lat": lat,
        "lng": lng,
        "cid": cid[0] + ":" + cid[1] if cid else None,
        "placeId": place_id,
    }


def write_json(places, out):
    path = f"{out}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(places, f, indent=2, ensure_ascii=False)
    return path


def write_csv(places, out):
    path = f"{out}.csv"
    fields = ["name", "label", "address", "lat", "lng", "cid", "placeId"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(places)
    return path


def write_geojson(places, out):
    path = f"{out}.geojson"
    features = []
    for p in places:
        if p["lat"] is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p["lng"], p["lat"]]},
            "properties": {k: v for k, v in p.items() if k not in ("lat", "lng")},
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, indent=2, ensure_ascii=False)
    return path


def _xml_escape(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def write_kml(places, out, list_title):
    path = f"{out}.kml"
    placemarks = []
    for p in places:
        if p["lat"] is None:
            continue
        placemarks.append(
            "  <Placemark>\n"
            f"    <name>{_xml_escape(p['name'])}</name>\n"
            f"    <description>{_xml_escape(p['address'])}</description>\n"
            f"    <Point><coordinates>{p['lng']},{p['lat']},0</coordinates></Point>\n"
            "  </Placemark>"
        )
    kml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        "<Document>\n"
        f"  <name>{_xml_escape(list_title or out)}</name>\n"
        + "\n".join(placemarks)
        + "\n</Document>\n</kml>\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(kml)
    return path


def write_gpx(places, out, list_title):
    """GPX, the standard format for GPS devices and apps like OsmAnd,
    Organic Maps, Garmin, etc. (more portable than KML for that use case)."""
    path = f"{out}.gpx"
    waypoints = []
    for p in places:
        if p["lat"] is None:
            continue
        waypoints.append(
            f'  <wpt lat="{p["lat"]}" lon="{p["lng"]}">\n'
            f"    <name>{_xml_escape(p['name'])}</name>\n"
            f"    <desc>{_xml_escape(p['address'])}</desc>\n"
            "  </wpt>"
        )
    gpx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="gmaps_list_export" xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <name>{_xml_escape(list_title or out)}</name>\n"
        + "\n".join(waypoints)
        + "\n</gpx>\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(gpx)
    return path


WRITERS = {
    "json": write_json,
    "csv": write_csv,
    "geojson": write_geojson,
    "kml": write_kml,
    "gpx": write_gpx,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="A Google Maps list share link (short maps.app.goo.gl/... or long)")
    ap.add_argument("--format", default="json", help="Comma-separated: json,csv,geojson,kml,gpx (default: json)")
    ap.add_argument("--out", default="places", help="Output filename without extension (default: places)")
    args = ap.parse_args()

    formats = [f.strip().lower() for f in args.format.split(",") if f.strip()]
    unknown = [f for f in formats if f not in WRITERS]
    if unknown:
        raise SystemExit(f"Unknown format(s): {', '.join(unknown)}. Available: {', '.join(WRITERS)}")

    print("Resolving list...", file=sys.stderr)
    list_id, token, opener = resolve_list(args.url)
    print(f"  list id:  {list_id}", file=sys.stderr)
    print(f"  token:    {token or '(none, publicly listed without one)'}", file=sys.stderr)

    print("Fetching places...", file=sys.stderr)
    list_title, raw_places = fetch_places(list_id, token, opener)
    places = [parse_place(p) for p in raw_places]
    missing = sum(1 for p in places if p["lat"] is None)
    print(f"  \"{list_title}\" - {len(places)} places ({missing} missing coordinates)", file=sys.stderr)

    for fmt in formats:
        writer = WRITERS[fmt]
        path = writer(places, args.out, list_title) if fmt in ("kml", "gpx") else writer(places, args.out)
        print(f"  wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
