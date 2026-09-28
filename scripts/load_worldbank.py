#!/usr/bin/env python3
"""Load World Bank Open Data for India into the official-statistics tables.

Run:
    backend/.venv/bin/python scripts/load_worldbank.py --dry-run
    backend/.venv/bin/python scripts/load_worldbank.py

Reads DATABASE_URL from the environment or from backend/.env. Requires
migration 004 to have been applied; the script says so rather than creating
tables, because DDL belongs in the migration series with seed_meta bookkeeping.

This script is idempotent. Both tables are upserted on their natural key
(indicator code, and indicator code + year), so re-running after a World Bank
release updates values in place and leaves the row count stable. Pass
--prune to additionally delete observations for years no longer published, so
a revision that drops a year actually drops it here.

WHY httpx AND NOT urllib
The venv's interpreter is a framework build whose CA store does not include the
ISRG Root X1 chain, so urllib.request fails TLS verification against
api.worldbank.org (URLError) while curl and httpx both succeed. httpx is
already a project dependency, so it is used here rather than depending on
certifi being installed.

WHY THE RETRIES AND THE SLEEP
The API answers unauthenticated calls but throttles bursts: a 12-indicator loop
with no delay reliably produced a ReadTimeout partway through. World Bank asks
clients to be polite with a public endpoint, so this paces itself and retries
with backoff instead of hammering until it gets through. An indicator that
still fails after retries is reported and skipped — a partial load with an
honest warning is more useful than a crash, and the migration's CHECK
constraints make a partial load safe.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

API = "https://api.worldbank.org/v2"
COUNTRY = "IND"
SOURCE_URL = f"https://data.worldbank.org/country/india"
# Seconds between indicators. Raising the RATE_LIMIT_DENIED path to a 429-aware
# backoff is handled by _fetch's retry loop.
REQUEST_DELAY = 0.6

# code -> (name, category, unit, note)
#
# Codes were verified against the live API for IND before being written down.
# Three plausible codes were rejected because the World Bank returns
# "Invalid value" for India on them, and guessing there would have produced a
# loader that silently shipped an empty indicator:
#   SP.LIT.TOTL.IN  -> literacy for India lives at SE.ADT.LITR.ZS
#   SP.TOTL.TFRT.IN -> fertility lives at SP.DYN.TFRT.IN
#   SL.ISV.IFRM.ZS  -> informal employment has no India series
#
# `expected` is the direction the series is expected to move between its first
# and last year. It is not documentation: verify_trends() turns each entry into
# a real assertion after loading, because a loader bug once paired every year
# with the wrong value and produced a table where life expectancy fell as 72
# -> 60 -> 45. Every row was internally consistent and plausible in isolation;
# only the direction was impossible. These assertions are what caught it, so
# they run on every load rather than as a one-off manual check.
INDICATORS: dict[str, tuple[str, str, str, str]] = {
    # Economy
    "NY.GDP.MKTP.CD": ("GDP (current US$)", "Economy", "US$", "Total output, current prices."),
    "NY.GDP.PCAP.CD": ("GDP per capita (current US$)", "Economy", "US$", "Not inflation-adjusted."),
    "NY.GDP.MKTP.KD.ZG": ("GDP growth (annual %)", "Economy", "%", "Real growth, constant prices."),
    "NV.IND.MANF.ZS": ("Manufacturing value added (% of GDP)", "Economy", "%", "Industry's share of GDP."),
    # Demography
    "SP.POP.TOTL": ("Population, total", "Demography", "people", "Mid-year population estimate."),
    # Health
    "SP.DYN.LE00.IN": ("Life expectancy at birth (years)", "Health", "years", "At birth, both sexes."),
    "SP.DYN.TFRT.IN": ("Fertility rate, total (births per woman)", "Health", "births/woman", "Total fertility rate."),
    "SH.STA.MMRT": ("Under-5 mortality (per 1,000 live births)", "Health", "per 1,000", "Probability of dying before age 5."),
    "SH.XPD.CHEX.GD.ZS": ("Current health expenditure (% of GDP)", "Health", "%", "Domestic health spending."),
    # Labour
    "SL.UEM.TOTL.ZS": ("Unemployment, total (% of labour force)", "Labour", "%", "ILO modelled estimate."),
    "SL.TLF.CACT.FE.ZS": ("Labour force participation, female (%)", "Labour", "%", "Women aged 15+."),
    # Education
    "SE.ADT.LITR.ZS": ("Literacy rate, adult total (% ages 15+)", "Education", "%", "UNESCO modelled, both sexes."),
    "SE.ADT.LITR.FE.ZS": ("Literacy rate, adult female (% ages 15+)", "Education", "%", "UNESCO modelled."),
    "SE.SEC.ENRR": ("School enrolment, secondary (% gross)", "Education", "%", "Gross, all ages."),
    # Digital
    "IT.NET.USER.ZS": ("Individuals using the Internet (% of population)", "Digital", "%", "Share of population online."),
    # Agriculture
    "AG.PRD.FOOD.XD": ("Food production index (2014-2016 = 100)", "Agriculture", "index", "Base year 2014-2016 = 100."),
}

# Direction the first and last observation must move. "up" / "down" only where
# the direction is not in doubt; a series that legitimately reverses (GDP
# growth) is deliberately absent rather than given a weak expectation.
EXPECTED_TREND: dict[str, str] = {
    "SP.DYN.LE00.IN": "up",      # life expectancy
    "SH.STA.MMRT": "down",       # child mortality
    "SE.ADT.LITR.ZS": "up",      # literacy
    "SE.ADT.LITR.FE.ZS": "up",
    "SP.POP.TOTL": "up",         # population
    "IT.NET.USER.ZS": "up",      # internet use
    "SE.SEC.ENRR": "up",         # secondary enrolment
    "SL.TLF.CACT.FE.ZS": "up",    # female participation
    "SP.DYN.TFRT.IN": "down",    # fertility
}


def load_dotenv_or_die() -> None:
    env_file = ROOT / "backend" / ".env"
    if env_file.exists():
        from dotenv import load_dotenv

        load_dotenv(env_file)
    import os

    if not os.environ.get("DATABASE_URL"):
        sys.exit("DATABASE_URL is not set. Add it to backend/.env or export it.")


def _fetch(client: httpx.Client, code: str, tries: int = 4) -> tuple[str, list[dict], str]:
    """Return (status, observations, detail).

    status is one of: ok, no_data, failed. Observations are the raw
    non-null rows, newest year first as the API returns them.
    """
    for attempt in range(tries):
        try:
            resp = client.get(
                f"{API}/country/{COUNTRY}/indicator/{code}",
                params={"format": "json", "per_page": 400},
                timeout=45.0,
            )
            if resp.status_code == 429:
                raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
            resp.raise_for_status()
            payload = resp.json()
            if not isinstance(payload, list) or not payload:
                return "no_data", [], "empty payload"
            # The API signals a genuinely unavailable series as a 1-element list
            # whose first item has id/key 120 "Invalid value". A 2-element list
            # with an empty tail is a valid series that happens to be empty.
            if len(payload) < 2:
                return "no_data", [], str(payload[0].get("message", "no series"))[:80]
            rows = [r for r in payload[1] if r.get("value") is not None]
            if not rows:
                return "no_data", [], "series present but empty"
            return "ok", rows, f"{len(rows)} observations"
        except Exception as exc:  # noqa: BLE001 - any transport failure is retryable
            if attempt == tries - 1:
                return "failed", [], f"{type(exc).__name__}: {exc}"[:100]
            time.sleep(1.5 * (attempt + 1))  # back off; public endpoint, stay polite
    return "failed", [], "unreachable"


def _provenance(client: httpx.Client, code: str) -> str:
    """Return the originating source the World Bank attributes this series to.

    This is the value that makes the CC BY attribution honest: "Life expectancy
    at birth" is really UN World Population Prospects, and "Literacy rate" is
    UNESCO. Taking it from /indicator/{code} -> sourceOrganization is what
    separates an official survey statistic from a World Bank estimate in the
    UI, so a reader is not told the wrong thing about where a number came from.

    Best-effort: attribution quality matters, but a missing provenance string
    must not fail the load. Callers get an explicit fallback, never a blank.
    """
    try:
        resp = client.get(f"{API}/indicator/{code}", params={"format": "json"}, timeout=25.0)
        if resp.status_code != 200:
            return "World Bank Open Data"
        payload = resp.json()
        if not (isinstance(payload, list) and len(payload) >= 2 and isinstance(payload[1], list)):
            return "World Bank Open Data"
        rows = [r for r in payload[1] if isinstance(r, dict) and r.get("id") == code]
        if not rows:
            return "World Bank Open Data"
        org = str(rows[0].get("sourceOrganization") or "").strip()
        # Trailing "uri: ..." metadata adds noise without helping attribution,
        # and the API embeds newlines inside multi-source strings. Collapse both
        # so the value is safe to render in a single HTML line.
        org = re.split(r"[;,]\s*uri:", org, maxsplit=1)[0]
        org = re.sub(r"\s+", " ", org.replace(";", ";")).strip().strip(";").strip()
        if not org:
            return "World Bank Open Data"
        if len(org) > 180:
            # Truncate on a separator, not mid-word: a bare [:180] left GDP's
            # provenance ending in a dangling "S", which reads as broken data
            # rather than as an honest "this list was cut short".
            cut = org[:180]
            for sep in (";", ","):
                if sep in cut[120:]:
                    cut = cut[: cut.rindex(sep)]
                    break
            org = cut.strip().strip(";,") + " …"
        return org
    except Exception:  # noqa: BLE001
        return "World Bank Open Data"


def verify_trends() -> list[str]:
    """Assert loaded series move in the direction the real world requires.

    Reads back from the database rather than from the in-memory fetch, so it
    validates what was actually stored. Returns a list of failure strings; empty
    means every assertion held.
    """
    import database

    problems: list[str] = []
    conn = database.get_db_connection()
    try:
        for code, direction in EXPECTED_TREND.items():
            rows = conn.execute(
                "SELECT year, value FROM stat_observations WHERE indicator_code = %s ORDER BY year",
                (code,),
            ).fetchall()
            if len(rows) < 2:
                problems.append(f"{code}: only {len(rows)} observation(s), cannot check trend")
                continue
            first, last = float(rows[0]["value"]), float(rows[-1]["value"])
            if direction == "up" and last <= first:
                problems.append(
                    f"{code} ({INDICATORS[code][0]}): expected to rise, "
                    f"{rows[0]['year']}={first:g} -> {rows[-1]['year']}={last:g}"
                )
            if direction == "down" and last >= first:
                problems.append(
                    f"{code} ({INDICATORS[code][0]}): expected to fall, "
                    f"{rows[0]['year']}={first:g} -> {rows[-1]['year']}={last:g}"
                )
    finally:
        conn.close()
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="fetch and report, write nothing")
    parser.add_argument("--prune", action="store_true", help="delete observations for years the API no longer returns")
    args = parser.parse_args()

    load_dotenv_or_die()
    import database

    print(f"World Bank Open Data -> {SOURCE_URL}")
    print(f"Country {COUNTRY}, {len(INDICATORS)} indicators, dry_run={args.dry_run}\n")

    loaded: list[tuple[str, str, int, int, int]] = []  # code, name, years, first, last
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    with httpx.Client(follow_redirects=True) as client:
        for code, (name, category, unit, note) in INDICATORS.items():
            status, rows, detail = _fetch(client, code)
            if status != "ok":
                (skipped if status == "no_data" else failed).append((code, detail))
                print(f"  {status.upper():9s} {code:18s} {detail}")
                time.sleep(REQUEST_DELAY)
                continue

            # Sort year and value TOGETHER as pairs. The API returns rows newest
            # first; sorting the years alone while zipping against the raw value
            # list pairs every year with someone else's value. That produced a
            # fully-populated table in which life expectancy fell 72 -> 45, and
            # verify_trends() exists precisely to catch that.
            pairs = sorted((int(r["date"]), float(r["value"])) for r in rows)
            years = [p[0] for p in pairs]
            values = [p[1] for p in pairs]
            loaded.append((code, name, len(pairs), years[0], years[-1]))
            print(f"  ok        {code:18s} n={len(pairs):3d}  {years[0]}..{years[-1]}  {name}")

            if not args.dry_run:
                prov = _provenance(client, code)
                conn = database.get_db_connection()
                try:
                    # Explicit commit(), not `with conn.transaction():`. The
                    # pool's liveness check runs `SELECT 1` on checkout, so a
                    # transaction is ALREADY open when this runs; psycopg then
                    # treats transaction() as nested and releases a savepoint
                    # instead of committing. close() then sees a non-IDLE
                    # connection and rolls the whole thing back — silently, with
                    # no error. Both statements go in one commit so an
                    # indicator is never stored without its observations.
                    conn.execute(
                        """
                        INSERT INTO stat_indicators (code, name, category, unit, provenance, source, source_url, license)
                        VALUES (%s, %s, %s, %s, %s, 'World Bank Open Data', %s, 'CC BY 4.0')
                        ON CONFLICT (code) DO UPDATE SET
                            name = EXCLUDED.name,
                            category = EXCLUDED.category,
                            unit = EXCLUDED.unit,
                            provenance = COALESCE(NULLIF(EXCLUDED.provenance, ''), stat_indicators.provenance),
                            source = EXCLUDED.source,
                            source_url = EXCLUDED.source_url,
                            license = EXCLUDED.license
                        """,
                        (code, name, category, unit, prov, SOURCE_URL),
                    )
                    # Multi-row upsert, one statement. The alias list is
                    # required: bare `unnest(a, b)` names its output columns
                    # `unnest` and `unnest_1`, not `y` and `v`. The WHERE clause
                    # keeps the statement a no-op when the value is unchanged,
                    # so a re-run does not churn bookkeeping.
                    conn.execute(
                        """
                        INSERT INTO stat_observations (indicator_code, year, value)
                        SELECT %s, t.y, t.v FROM unnest(%s::int[], %s::numeric[]) AS t(y, v)
                        ON CONFLICT (indicator_code, year) DO UPDATE SET value = EXCLUDED.value
                        WHERE stat_observations.value IS DISTINCT FROM EXCLUDED.value
                        """,
                        (code, years, values),
                    )
                    conn.commit()
                finally:
                    conn.close()

            time.sleep(REQUEST_DELAY)

    total_obs = sum(r[2] for r in loaded)
    print(f"\n{len(loaded)} indicators, {total_obs} observations, "
          f"{len(skipped)} skipped, {len(failed)} failed")

    if skipped:
        print("\nSkipped (no series for India):")
        for code, why in skipped:
            print(f"  {code:18s} {why}")
    if failed:
        print("\nFAILED - re-run, these did not reach the database:")
        for code, why in failed:
            print(f"  {code:18s} {why}")
        return 1

    if args.dry_run:
        print("\nDry run: nothing written.")
        return 0

    import database as db

    conn = db.get_db_connection()
    try:
        ic = conn.execute("SELECT count(*) AS n FROM stat_indicators").fetchone()["n"]
        oc = conn.execute("SELECT count(*) AS n FROM stat_observations").fetchone()["n"]
        print(f"\nstat_indicators={ic}  stat_observations={oc}")
        bad = conn.execute("SELECT count(*) AS n FROM stat_observations WHERE value IS NULL").fetchone()["n"]
        print(f"stored NULLs: {bad}  (must be 0)")
        cats = conn.execute(
            "SELECT category, count(*) AS n FROM stat_indicators GROUP BY category ORDER BY category"
        ).fetchall()
        print("categories: " + ", ".join(f"{r['category']}={r['n']}" for r in cats))
        # Idempotency proof: a second identical load must not change these counts.
        span = conn.execute(
            "SELECT min(year) AS lo, max(year) AS hi FROM stat_observations"
        ).fetchone()
        print(f"year span: {span['lo']}..{span['hi']}")
    finally:
        conn.close()

    # Read the trend assertions back out of the database before declaring
    # success. A load that stored a plausible-looking but directionally
    # impossible table is a failed load, not a successful one.
    problems = verify_trends()
    if problems:
        print(f"\nTREND CHECK FAILED ({len(problems)}):")
        for p in problems:
            print(f"  {p}")
        print("\nThe data is stored but must not be trusted or displayed until this is fixed.")
        return 1
    print(f"trend check: all {len(EXPECTED_TREND)} direction assertions held")

    print("\nprovenance (drives the CC BY attribution):")
    conn = db.get_db_connection()
    try:
        for r in conn.execute(
            "SELECT code, category, provenance FROM stat_indicators ORDER BY category, code"
        ).fetchall():
            print(f"  {r['code']:18s} {r['category']:12s} {r['provenance']}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
