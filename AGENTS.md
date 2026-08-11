# AGENTS.md

Instructions for an AI coding agent using this repo. For human-readable docs, see [README.md](README.md) in this repo.

## What this does

`gmaps_list_export.py` converts a Google Maps list share link into structured place data (name, address, lat, lng, and Google's internal CID and placeId). It works on lists the requesting user does not own, including lists they only joined. It requires no API key, no browser, and no authentication for a publicly shared list.

## When to use this

Use this script whenever a user asks to:
- export, dump, or scrape a Google Maps list
- get coordinates or lat/lng out of a Google Maps list
- convert a Google Maps list to CSV, JSON, GeoJSON, KML, or GPX
- get data from a Google Maps list they don't own or only joined
- work around Google Takeout not showing a joined list (Takeout only exports lists the user created)

## How to run it

1. Get the script: `gmaps_list_export.py` in this repo. Python 3, standard library only, no `pip install` needed.
2. Get the list URL from the user: either a short link (`https://maps.app.goo.gl/XXXXXXXX`) or a long `google.com/maps/...` list URL. Both work unmodified.
3. Run:

```bash
python3 gmaps_list_export.py "<url>" --format json,csv,geojson,kml,gpx --out places
```

`--format` is comma-separated, any subset of `json,csv,geojson,kml,gpx`. Default is `json` alone if omitted. `--out` sets the output filename base (default `places`); output files are `<out>.<format>`.

4. Read back `<out>.json` (or whichever format is most useful for the task) to get structured data: a list of objects with `name`, `label`, `address`, `lat`, `lng`, `cid`, `placeId`.

## Error handling

- `SystemExit: Couldn't find a list id in the resolved URL`: the URL is not a Maps list link (a single place or plain map view instead). Ask the user to confirm the link points at a list, not a place.
- `json.loads` failure or `urllib.error.HTTPError`: the list likely requires the viewer to be signed in as a collaborator, meaning it is not truly public. Tell the user to check the list's sharing setting, or verify it opens in an incognito browser window without a sign-in prompt.
- A run that returns fewer places than the user expects: the underlying API caps at 500 entries per call (`4i500` in the script). Not tested past that size; flag this to the user rather than assuming the output is complete.

## Constraints, do not change these

- Do not remove or "clean up" `SHORTLINK_USER_AGENT = "Mozilla/5.0"` in the script, or replace it with a full modern browser user agent string. The short-link redirect only returns a plain HTTP redirect for a bare, unremarkable user agent; a full Chrome UA makes Google serve a JS interstitial instead, and the script breaks.
- Do not add authentication, an API key, or a login flow. None is needed or supported.
- This calls an undocumented Google endpoint (`/maps/preview/entitylist/getlist`), not a public API. If it starts failing entirely (not just on one bad URL), the endpoint may have changed; do not assume the script's logic is wrong before checking that.
