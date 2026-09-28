"""Official-statistics routes — the World Bank dataset behind the SQL/Python labs.

Exposes the two tables created by 004_worldbank_indicators.sql:

    GET /api/stats/indicators          catalogue, with a year span per indicator
    GET /api/stats/series/{code}       one indicator's observations over time
    GET /api/stats/compare?codes=a,b   several indicators normalised to index 100
    GET /api/stats/categories          grouped counts for filter UIs

WHAT THIS DATA IS, AND WHY EVERY RESPONSE REPEATS THE ATTRIBUTION
This is World Bank Open Data for India, published under CC BY 4.0, which
requires attribution. `_indicator_public()` therefore stamps `source`,
`source_url`, `license` and `provenance` onto every indicator object rather
than exposing the licence on one "about" endpoint that a user may never open.
A statistics product that shows a number without saying where it came from is
the failure mode this is designed to prevent.

It is also not "Indian government data" in the sense a user might assume. The
World Bank republishes and extends figures that originate with the national
statistical system and adds its own estimates, so `provenance` is returned
alongside every series to let a reader tell the difference — "National
Statistical Offices" for GDP, "UN World Population Prospects" for life
expectancy. Presenting all of it as government statistics would be wrong.

AUTHORISATION
These tables are public reference data with no user_id, so any signed-in user
may read them. `current_identity` is still required on every route: the dataset
is the lab's teaching material, and an unsigned visitor should not be able to
enumerate it. Reads never commit (see the note on _PooledConnection.close in
database.py), so no write path exists here at all.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth_tokens import Identity, current_identity
from database import get_db_connection

router = APIRouter(prefix="/api/stats", tags=["stats"])

MAX_COMPARE_CODES = 6
MAX_SERIES_POINTS = 500


class CategoryCount(BaseModel):
    category: str
    indicator_count: int
    observation_count: int


def _indicator_public(row: dict) -> dict:
    """Strip internal columns and force the attribution fields to be present.

    `provenance` falls back to the source name rather than to None so the
    frontend never has to render an empty "Source:" line — an attribution
    widget that can render blank is an attribution widget nobody reads.
    """
    return {
        "code": row["code"],
        "name": row["name"],
        "category": row["category"],
        "unit": row.get("unit"),
        "provenance": row.get("provenance") or row["source"],
        "source": row["source"],
        "source_url": row["source_url"],
        "license": row["license"],
        "first_year": row.get("first_year"),
        "last_year": row.get("last_year"),
        "observation_count": row.get("observation_count"),
    }


def _num(value) -> Optional[float]:
    """Coerce NUMERIC to float for JSON.

    psycopg returns NUMERIC as Decimal, which json.dumps cannot serialise.
    Rounding to 4dp keeps a GDP figure like 2702.4798714 from shipping 12
    meaningless digits to the browser; full precision stays in the database.
    """
    return None if value is None else round(float(value), 4)


@router.get("/indicators")
def list_indicators(
    category: Optional[str] = Query(None, max_length=40),
    identity: Identity = Depends(current_identity),
):
    """The indicator catalogue, optionally filtered to one category.

    The year span and observation count ride along so a UI can say "1960-2025,
    66 points" without a second request per row.
    """
    sql = """
        SELECT i.code, i.name, i.category, i.unit, i.provenance,
               i.source, i.source_url, i.license,
               min(o.year) AS first_year,
               max(o.year) AS last_year,
               count(o.year) AS observation_count
          FROM stat_indicators i
          LEFT JOIN stat_observations o ON o.indicator_code = i.code
    """
    params: list = []
    if category:
        # Lowercased on both sides so the category filter is case-insensitive,
        # matching how the frontend's own category list is cased.
        sql += " WHERE lower(i.category) = lower(%s)"
        params.append(category)
    sql += " GROUP BY i.code, i.name, i.category, i.unit, i.provenance, i.source, i.source_url, i.license"
    sql += " ORDER BY i.category, i.name"

    conn = get_db_connection()
    try:
        # The list is passed as ONE sequence argument, not unpacked with *params.
        # Unpacking turns `params=['Health']` into a bare str, which psycopg
        # rejects with "query parameters should be a sequence or a mapping, got
        # str" — and, being a TypeError raised before any SQL runs, it surfaces
        # as a 500 rather than anything a caller could act on.
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    return {"count": len(rows), "indicators": [_indicator_public(r) for r in rows]}


@router.get("/categories")
def list_categories(identity: Identity = Depends(current_identity)):
    """Indicator and observation counts per category, for filter chips."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT i.category,
                   count(DISTINCT i.code) AS indicator_count,
                   count(o.year)       AS observation_count
              FROM stat_indicators i
              LEFT JOIN stat_observations o ON o.indicator_code = i.code
             GROUP BY i.category
             ORDER BY i.category
            """
        ).fetchall()
    finally:
        conn.close()

    return {
        "categories": [
            CategoryCount(
                category=r["category"],
                indicator_count=r["indicator_count"],
                observation_count=r["observation_count"],
            )
            for r in rows
        ]
    }


@router.get("/series/{code}")
def get_series(
    code: str,
    start_year: Optional[int] = Query(None, ge=1800, le=2200),
    end_year: Optional[int] = Query(None, ge=1800, le=2200),
    identity: Identity = Depends(current_identity),
):
    """Observations for one indicator, oldest first.

    The code is a path segment, so it is bound as a parameter and never
    interpolated. An unknown code is a 404 rather than an empty series: the lab
    needs to tell "this indicator has no data" apart from "this indicator does
    not exist", and a silent empty list teaches the wrong lesson.
    """
    if start_year is not None and end_year is not None and start_year > end_year:
        raise HTTPException(status_code=400, detail="start_year must not exceed end_year")

    conn = get_db_connection()
    try:
        indicator = conn.execute(
            "SELECT code, name, category, unit, provenance, source, source_url, license "
            "FROM stat_indicators WHERE code = %s",
            (code,),
        ).fetchone()
        if indicator is None:
            # Truncated before echoing. The value is bound, so it cannot execute
            # anything, but an error body is still a reflection point and has no
            # reason to return an arbitrarily long attacker-controlled string.
            raise HTTPException(
                status_code=404, detail=f"Unknown indicator code: {code[:60]}"
            )

        sql = "SELECT year, value FROM stat_observations WHERE indicator_code = %s"
        params: list = [code]
        if start_year is not None:
            sql += " AND year >= %s"
            params.append(start_year)
        if end_year is not None:
            sql += " AND year <= %s"
            params.append(end_year)
        sql += " ORDER BY year"

        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    if len(rows) > MAX_SERIES_POINTS:
        rows = rows[-MAX_SERIES_POINTS:]

    return {
        "indicator": _indicator_public(indicator),
        "count": len(rows),
        # Points, not raw tuples: the SQL lab teaches charting, so the payload
        # should not require the frontend to invent the {x,y} shape.
        "points": [{"year": r["year"], "value": _num(r["value"])} for r in rows],
    }


@router.get("/compare")
def compare(
    codes: str = Query(..., min_length=1, max_length=400),
    base_year: Optional[int] = Query(None, ge=1800, le=2200),
    identity: Identity = Depends(current_identity),
):
    """Several indicators rebased to 100 at a common year.

    GDP in rupees and life expectancy in years cannot share a y-axis. Rebasing
    every series to 100 at the first year they all have data is what makes a
    single comparison chart honest, and it is the exercise the Data
    Visualization Lab assigns.

    `base_year` defaults to the latest year present in *every* requested
    series, so a sparse series is not silently anchored to a year its neighbours
    have not reached. Years missing from one series are returned as null rather
    than dropped, so the chart shows the gap instead of interpolating over it.
    """
    wanted = [c.strip() for c in codes.split(",") if c.strip()]
    if not wanted:
        raise HTTPException(status_code=400, detail="No indicator codes supplied")
    if len(wanted) > MAX_COMPARE_CODES:
        raise HTTPException(
            status_code=400, detail=f"At most {MAX_COMPARE_CODES} indicators can be compared"
        )
    if len(set(wanted)) != len(wanted):
        raise HTTPException(status_code=400, detail="Duplicate indicator codes")

    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT i.code, i.name, i.category, i.unit, i.provenance,
                   i.source, i.source_url, i.license,
                   o.year, o.value
              FROM stat_indicators i
              JOIN stat_observations o ON o.indicator_code = i.code
             WHERE i.code = ANY(%s)
             ORDER BY i.code, o.year
            """,
            (wanted,),
        ).fetchall()
    finally:
        conn.close()

    found = {r["code"] for r in rows}
    missing = [c for c in wanted if c not in found]
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown indicator code(s): {', '.join(missing)[:120]}",
        )

    by_code: dict[str, list] = {}
    meta: dict[str, dict] = {}
    for r in rows:
        by_code.setdefault(r["code"], []).append((r["year"], float(r["value"])))
        if r["code"] not in meta:
            meta[r["code"]] = _indicator_public(r)

    if base_year is not None:
        anchor = base_year
    else:
        # Latest year that every series actually has an observation for.
        common = set(y for y, _ in by_code[wanted[0]])
        for c in wanted[1:]:
            common &= {y for y, _ in by_code[c]}
        if not common:
            raise HTTPException(
                status_code=409,
                detail="These indicators share no common year; pass base_year explicitly",
            )
        anchor = max(common)

    series = []
    for c in wanted:
        base_value = next((v for y, v in by_code[c] if y == anchor), None)
        series.append(
            {
                "indicator": meta[c],
                "base_year": anchor,
                "base_value": None if base_value is None else _num(base_value),
                "points": [
                    {
                        "year": y,
                        "value": _num(v),
                        # None when this series has no value at the anchor year.
                        # Emitting 0.0 here would draw a line from zero and imply
                        # a collapse that never happened.
                        "indexed": None if base_value in (None, 0) else round(v / base_value * 100, 4),
                    }
                    for y, v in by_code[c]
                ],
            }
        )

    return {"base_year": anchor, "count": len(series), "series": series}
