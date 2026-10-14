CALIBRATED GOLF — EUMETSAT LIVE LIGHTNING FEED (v8.8.92 TEST)
===============================================================

CURRENT STATUS: OFFLINE TEST / NOT YET A LIVE EUMETSAT CONNECTION.
This is a starter pipeline. Credentials, NRT access rights, a publisher,
source-file decoding and live timeliness still require end-to-end validation.
DO NOT replace the approved master for golfing safety before those checks pass.

What it does:
* EUMDAC requests EUMETSAT MTG LI-2-LFL lightning-flash products.
* A scheduled Python job parses flash latitude, longitude and time from NetCDF4.
* It publishes one small public JSON file for the whole of southern Africa.
* Every golfer reads the SAME data (rather than each golfer calling EUMETSAT).
* The app measures each flash's distance to the selected course and preserves
  the existing 25km / 50km / 100km warning logic.
* Lightning detected within clouds counts too. All types are proximity signals.
* If feed is old, partial, blocked or offline: GREY DATA UNAVAILABLE, never green.

STEP 1 — EUMETSAT account (no API credentials in chat or Index.html)
1. Register or sign in at https://user.eumetsat.int/
2. In your EUMETSAT Data Store account, confirm whether you can download
   latest (near-real-time) "LI Lightning Flashes - MTG - 0 degree" data
   collection EO:EUM:DAT:0691. NRT downloads may require an active license
   even where the catalogue labels the data policy "NoConditions".
3. Create an API consumer KEY and SECRET: https://api.eumetsat.int/api-key
   Store them ONLY as GitHub repository secrets in the dedicated feed repo.

STEP 2 — Create a separate public GitHub repository for the FEED ONLY
1. Make a new public repository, e.g. calibrated-golf-lightning-feed.
2. Put the CONTENTS of this EUMETSAT_Feed folder at the repository root,
   preserving the .github/workflows folder. Don't put the private app source
   or API keys in that public repository.
3. In Settings > Secrets and variables > Actions add these two secrets:
   EUMETSAT_CONSUMER_KEY and EUMETSAT_CONSUMER_SECRET.
   In Settings > Pages, choose Build and deployment > GitHub Actions.
   Run the "EUMETSAT MTG LI lightning feed" workflow manually ONCE.

STEP 3 — Validate feed, then connect the app
1. Open Actions, inspect the workflow result and its published GitHub Pages
   site; a completed feed should contain "complete":true, recent timestamps,
   and "source":"EUMETSAT-MTG-LI-LFL". A "complete":false feed is NOT LIVE.
2. Your public URL will look like:
   https://YOUR-GITHUB-USERNAME.github.io/calibrated-golf-lightning-feed/latest.json
3. Once that real URL is working, find the human-readable line near
   the TOP of Index.html:
       window.CG_EUMETSAT_FEED_URL = '';
   and set it to the real public URL. Do not put your EUMETSAT keys in HTML.
   We can make this final single-line change together after you have the URL.

NOTE ON FREE SCHEDULING AND SAFE GOLF:
GitHub Actions scheduled jobs and GitHub Pages are convenient for a free TEST,
but GitHub explicitly warns that scheduled jobs can be delayed or dropped.
They are NOT a guaranteed low-latency operational feed, even when the satellite
itself is operational. If data is not fresh the app intentionally warns that
lightning data is unavailable. No lightning system can guarantee player safety;
follow local weather service alerts and seek shelter when thunder is heard.

Map renderer: ONLY MapLibre GL JS; basemap: Maptoolkit Community Hiking.
Maptoolkit requires a visible logo and copyright attribution; the map is best-
effort and must not be relied on as the safety-critical alert mechanism.

Source descriptions:
https://api.eumetsat.int/data/browse/collections/EO:EUM:DAT:0691?format=html
https://gitlab.eumetsat.int/eumetlab/data-services/eumdac_data_store
https://docs.maptoolkit.org/attribution/

Files in this folder:
 scripts/update_lightning.py    data extraction (EUMDAC + netCDF4)
 requirements.txt               dependencies for GitHub Actions
 .github/workflows/...          5-minute best-effort schedule + Pages publish
 public/latest.json             initial unavailable placeholder
 tests/test_feed.py             coverage and fail-closed tests
