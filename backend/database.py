"""PostgreSQL (Supabase) access layer for SakshamAI.

The schema, migrations and seed live in supabase/migrations/*.sql. This module
owns exactly three things: a connection pool, the migration runner, and the
canonical reference data that scripts/export_seed.py generates the seed from.

Previously this was a local SQLite file (sakshamai.db), which meant data only
existed on one machine and vanished on re-clone. Everything now lives in
Supabase, so any device sees the same rows.

Why psycopg and not supabase-py: the backend is raw SQL throughout (108
execute() calls). supabase-py goes through PostgREST, which has no
multi-statement transactions — and routers/assessment.py::_persist_questions
does a DELETE followed by 18 INSERTs that must land atomically. A direct
connection keeps the SQL as SQL. See supabase/migrations/002_rls.sql for why
this also means RLS is not the active access-control boundary.

The pool deliberately runs in psycopg's default mode (autocommit off) so that
the explicit conn.commit() calls already scattered through the routers keep
their meaning, and conn.close() returns the connection to the pool.
"""

import json
import logging
import os
from pathlib import Path

from psycopg import OperationalError
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from log_safety import safe_exception

logger = logging.getLogger("sakshamai.db")

BACKEND_DIR = Path(__file__).parent
MIGRATIONS_DIR = BACKEND_DIR.parent / "supabase" / "migrations"

_pool: ConnectionPool | None = None


class DatabaseNotConfigured(RuntimeError):
    """Raised when DATABASE_URL is missing, with the fix in the message."""

# ---------------------------------------------------------------- competencies
# (id, name, category, description)
COMPETENCIES = [
    # Statistical (10)
    ("survey-design", "Survey Design", "Statistical", "Designing effective surveys and data collection instruments"),
    ("sampling", "Sampling", "Statistical", "Statistical sampling methodologies and techniques"),
    ("data-quality", "Data Quality", "Statistical", "Data quality frameworks, validation, verification and reconciliation"),
    ("national-accounts", "National Accounts", "Statistical", "Compilation of national accounts and GDP estimates"),
    ("price-statistics", "Price Statistics", "Statistical", "Price statistics, CPI/WPI construction and inflation measurement"),
    ("labour-statistics", "Labour Statistics", "Statistical", "Labour force surveys, employment and workforce statistics"),
    ("agricultural-statistics", "Agricultural Statistics", "Statistical", "Agricultural production, land use and crop statistics"),
    ("industrial-statistics", "Industrial Statistics", "Statistical", "Industrial production and enterprise statistics"),
    ("sdg-indicators", "SDG Indicators", "Statistical", "SDG indicator frameworks, baselines and monitoring"),
    ("metadata-standards", "Metadata Standards", "Statistical", "Statistical metadata standards and data documentation (DDI/SDMX)"),
    # Technical (11)
    ("python", "Python", "Technical", "Programming in Python for data analysis and automation"),
    ("r", "R", "Technical", "Statistical computing and graphics with R"),
    ("sql", "SQL", "Technical", "Database querying and management with SQL"),
    ("stata", "Stata", "Technical", "Econometric analysis using Stata"),
    ("spss", "SPSS", "Technical", "Statistical data processing with SPSS"),
    ("sas", "SAS", "Technical", "Enterprise statistical analysis with SAS"),
    ("gis", "GIS", "Technical", "Geographic information systems and spatial analysis"),
    ("data-visualization", "Data Visualization", "Technical", "Creating visual representations of data insights"),
    ("ai-ml", "AI/ML", "Technical", "Artificial Intelligence and Machine Learning fundamentals"),
    ("cloud-computing", "Cloud Computing", "Technical", "Cloud platforms, meghraj and managed services"),
    ("api-open-data", "APIs and Open Data", "Technical", "Building APIs and publishing open government data"),
    # Digital Governance (5)
    ("cybersecurity", "Cybersecurity", "Digital Governance", "Protecting systems and data from digital threats"),
    ("data-privacy", "Data Privacy", "Digital Governance", "Data protection regulations and privacy practices (DPDP)"),
    ("digital-signatures", "Digital Signatures", "Digital Governance", "Digital signatures and e-signature workflows"),
    ("government-cloud", "Government Cloud", "Digital Governance", "Government cloud (Meghraj), GI Cloud and shared infrastructure"),
    ("digital-public-infra", "Digital Public Infrastructure", "Digital Governance", "DPI building blocks - Aadhaar, UPI, DigiLocker, API sets"),
    # Behavioural (6)
    ("communication", "Communication", "Behavioural", "Effective verbal and written communication skills"),
    ("leadership", "Leadership", "Behavioural", "Leading teams and driving organizational change"),
    ("project-management", "Project Management", "Behavioural", "Planning and executing projects effectively"),
    ("ethics", "Ethics", "Behavioural", "Ethical conduct, integrity and anti-corruption practices"),
    ("decision-making", "Decision Making", "Behavioural", "Evidence-based and analytical decision making"),
    ("change-management", "Change Management", "Behavioural", "Managing organizational change and transformation"),
]

ALL_COMP_IDS = [c[0] for c in COMPETENCIES]

# ---------------------------------------------------------------- roles
# Base level for every competency, then per-role overrides.
BASE_ROLE_LEVEL = 2
ROLE_OVERRIDES = {
    "Statistical Investigator": {
        "survey-design": 4, "sampling": 4, "data-quality": 4,
        "python": 2, "sql": 2, "data-visualization": 3,
        "cybersecurity": 2, "data-privacy": 3,
        "communication": 4, "project-management": 3,
        "national-accounts": 3, "price-statistics": 3, "labour-statistics": 3,
        "agricultural-statistics": 3,
    },
    "Data Analyst": {
        "survey-design": 2, "sampling": 2, "data-quality": 3,
        "python": 4, "sql": 4, "data-visualization": 4, "ai-ml": 3,
        "r": 3, "stata": 2,
        "cybersecurity": 1, "data-privacy": 2,
        "communication": 3, "project-management": 2,
        "decision-making": 4, "api-open-data": 3,
    },
    "Senior Statistical Officer": {
        "survey-design": 4, "sampling": 5, "data-quality": 4,
        "national-accounts": 4, "price-statistics": 4, "labour-statistics": 4,
        "agricultural-statistics": 4, "industrial-statistics": 4,
        "sdg-indicators": 4, "metadata-standards": 4,
        "python": 3, "sql": 3, "data-visualization": 3, "ai-ml": 2,
        "cybersecurity": 3, "data-privacy": 4,
        "communication": 5, "leadership": 4, "project-management": 4,
        "ethics": 5, "decision-making": 4, "change-management": 4,
    },
    "Economic Statistician": {
        "national-accounts": 5, "price-statistics": 4, "industrial-statistics": 4,
        "survey-design": 3, "sampling": 4, "data-quality": 4,
        "stata": 4, "r": 3, "python": 3, "data-visualization": 3,
        "communication": 4, "ethics": 4, "decision-making": 4,
        "sdg-indicators": 4, "metadata-standards": 3,
    },
    "Price Statistics Officer": {
        "price-statistics": 5, "survey-design": 4, "sampling": 4, "data-quality": 4,
        "industrial-statistics": 3, "national-accounts": 3,
        "stata": 3, "spss": 3, "python": 2, "data-visualization": 3,
        "communication": 3, "ethics": 3,
    },
    "Labour Statistics Officer": {
        "labour-statistics": 5, "survey-design": 4, "sampling": 4, "data-quality": 4,
        "agricultural-statistics": 3, "sdg-indicators": 4,
        "stata": 3, "spss": 3, "python": 2, "data-visualization": 3,
        "communication": 3, "ethics": 3,
    },
    "Agricultural Statistics Officer": {
        "agricultural-statistics": 5, "labour-statistics": 3, "survey-design": 4,
        "sampling": 4, "data-quality": 4, "gis": 4, "sdg-indicators": 3,
        "stata": 3, "spss": 3, "python": 2, "data-visualization": 3,
        "communication": 3, "ethics": 3,
    },
    "District Statistical Officer": {
        "survey-design": 4, "sampling": 4, "data-quality": 4,
        "national-accounts": 3, "price-statistics": 3, "labour-statistics": 3,
        "agricultural-statistics": 3, "industrial-statistics": 3,
        "sdg-indicators": 4, "metadata-standards": 3,
        "python": 2, "sql": 2, "data-visualization": 3, "gis": 3,
        "cybersecurity": 3, "data-privacy": 3,
        "communication": 4, "leadership": 3, "project-management": 4,
        "ethics": 4, "change-management": 3,
    },
    "IT and Systems Officer": {
        "python": 5, "sql": 5, "cloud-computing": 5, "api-open-data": 4,
        "cybersecurity": 5, "data-privacy": 4, "digital-signatures": 4,
        "government-cloud": 4, "digital-public-infra": 4,
        "ai-ml": 4, "data-visualization": 4, "data-quality": 3,
        "project-management": 4, "communication": 3, "ethics": 4, "change-management": 4,
    },
}


def build_role_requirements():
    rows = []
    for role, overrides in ROLE_OVERRIDES.items():
        for cid in ALL_COMP_IDS:
            level = overrides.get(cid, BASE_ROLE_LEVEL)
            rows.append((role, cid, level))
    return rows


ROLE_REQUIREMENTS = build_role_requirements()

# ---------------------------------------------------------------- courses
# Modules are embedded as JSON in each course.
def _mod(title, duration, mtype, summary, code=None, sandbox=None):
    m = {"title": title, "duration": duration, "type": mtype, "summary": summary}
    if code:
        m["code"] = code
    if sandbox:
        m["sandbox"] = sandbox
    return m


PY_BASICS = """ages = [28, 34, 29, 41, 36]
total = 0
for a in ages:
    total += a
print('Count:', len(ages))
print('Sum:', total)
print('Mean age:', round(total / len(ages), 2))"""

PY_PANDAS = """survey = [
    {'district': 'Alwar', 'households': 420, 'dept': 'NSSO'},
    {'district': 'Mysuru', 'households': 515, 'dept': 'Census'},
    {'district': 'Nashik', 'households': 310, 'dept': 'NSSTA'},
    {'district': 'Ludhiana', 'households': 600, 'dept': 'NSSO'},
]
nss = [r['households'] for r in survey if r['dept'] == 'NSSO']
print('NSSO rows:', len(nss))
print('Average NSSO households:', round(sum(nss) / len(nss), 1))"""

PY_CLEAN = """raw = ['3.1', None, '2.8', '3.6', 'x', '3.9']
cleaned = []
for v in raw:
    try:
        cleaned.append(float(v))
    except (TypeError, ValueError):
        print('Dropped bad value:', v)
print('Cleaned values:', cleaned)
print('Mean of clean data:', round(sum(cleaned) / len(cleaned), 2))"""

PY_REPORT = """titles = ['Alwar', 'Mysuru', 'Nashik']
rates = [70.7, 72.6, 80.9]
print('District | Literacy | Status')
for d, r in zip(titles, rates):
    status = 'High' if r >= 75 else 'Needs focus'
    print(f'{d:8s} | {r:8.1f} | {status}')
print('Average literacy:', round(sum(rates) / len(rates), 1))"""

PY_ML = """pairs = [(1, 12), (2, 15), (3, 17), (4, 20), (5, 22), (6, 25)]
xs = [p[0] for p in pairs]
ys = [p[1] for p in pairs]
n = len(xs)
xbar = sum(xs) / n
ybar = sum(ys) / n
slope = sum((x - xbar) * (y - ybar) for x, y in pairs) / sum((x - xbar) ** 2 for x in xs)
intercept = ybar - slope * xbar
print('Slope:', round(slope, 3))
print('Intercept:', round(intercept, 2))
print('Predicted score after 8h:', round(slope * 8 + intercept, 1))"""

PY_CLUSTER = """census = [
    ('Alwar', 70.7),
    ('Mysuru', 72.6),
    ('Nashik', 80.9),
    ('Ludhiana', 82.2),
    ('Varanasi', 70.3),
]
scores = [r[1] for r in census]
mean_score = sum(scores) / len(scores)
for name, score in census:
    label = 'high' if score >= mean_score else 'low'
    print(name, '-> ' + label, '(mean', round(mean_score, 1), ')')"""

SQL_HIGH = "SELECT name, literacy FROM districts WHERE literacy > 75 ORDER BY literacy DESC"
SQL_AGG = "SELECT AVG(literacy) FROM districts"


COURSES = [
    ("course-1", "NSSTA-TPAC-101", "Fundamentals of Official Statistics", "NSSTA",
     "Comprehensive introduction to official statistics, principles, frameworks and practices used in national statistical systems.",
     json.dumps(["Survey Design", "Sampling", "Data Quality", "Metadata Standards"]), "Beginner", "8 weeks", "English", 4.5, "📊", "Statistical",
     json.dumps([
         _mod("Introduction to Official Statistical System", "1h", "lesson", "Overview of the National Statistical Office and statistical system of India"),
         _mod("Statistical Principles & Methodologies", "2h", "lesson", "Fundamental principles, definitions and classifications"),
         _mod("Data Quality Frameworks", "1h", "lesson", "Quality dimensions, data quality assessment frameworks"),
         _mod("Metadata & Dissemination Standards", "1h", "lesson", "Statistical metadata standards, documentation practices"),
         _mod("Fundamentals Assessment", "30m", "quiz", "Quick knowledge check on core concepts"),
     ])),
    ("course-2", "NSSTA-TPAC-202", "Survey Design and Sampling", "NSSTA",
     "Advanced course on survey methodology including questionnaire design, sampling frames, stratified sampling and estimation.",
     json.dumps(["Survey Design", "Sampling", "Data Quality"]), "Intermediate", "6 weeks", "English", 4.7, "🎯", "Statistical",
     json.dumps([
         _mod("Sampling Frames & Design", "2h", "lesson", "Building sampling frames and choosing survey designs"),
         _mod("Questionnaire Development", "1.5h", "lesson", "Question design, pretesting and cognitive interviewing"),
         _mod("Stratified & Cluster Sampling", "2h", "lesson", "Variance estimation for complex sample designs"),
         _mod("Survey Operations & Field Work", "1h", "lab", "Field operations and non-sampling error control"),
         _mod("Survey Design Project", "45m", "quiz", "Design a survey for a given objective"),
     ])),
    ("course-3", "NSSTA-TPAC-203", "National Accounts Compilation", "NSSTA",
     "Compilation of national accounts, GDP estimates and SNA frameworks for official statistics.",
     json.dumps(["National Accounts", "Data Quality", "Metadata Standards"]), "Advanced", "10 weeks", "English", 4.6, "💹", "Statistical",
     json.dumps([
         _mod("System of National Accounts (SNA)", "3h", "lesson", "SNA framework and accounting identities"),
         _mod("GDP Estimation Methods", "3h", "lesson", "Production, income and expenditure approaches"),
         _mod("Blue Book Compilation", "2h", "lab", "Hands-on compilation exercise from source data"),
         _mod("Revisions & Quality Assurance", "1.5h", "lesson", "Benchmarking, revisions policy and QA"),
     ])),
    ("course-4", "NSSTA-TPAC-204", "Price Statistics and CPI/WPI", "NSSTA",
     "Construction of Consumer Price Index (CPI), Wholesale Price Index (WPI) and inflation measurement.",
     json.dumps(["Price Statistics", "Sampling", "Data Quality"]), "Intermediate", "5 weeks", "English", 4.4, "🏷️", "Statistical",
     json.dumps([
         _mod("Index Number Theory", "2h", "lesson", "Laspeyres, Paasche and Fisher index formulas"),
         _mod("CPI Construction", "2h", "lab", "Compute CPI from price quotations"),
         _mod("Inflation Measurement & Uses", "1.5h", "lesson", "Interpreting inflation and its policy uses"),
     ])),
    ("course-5", "NSSTA-TPAC-205", "Labour and Agricultural Statistics", "NSSTA",
     "Labour force surveys, employment statistics and agricultural statistics compilation.",
     json.dumps(["Labour Statistics", "Agricultural Statistics", "Survey Design", "Sampling"]), "Intermediate", "6 weeks", "English", 4.3, "🌾", "Statistical",
     json.dumps([
         _mod("Labour Force Surveys (PLFS)", "2h", "lesson", "Survey design of PLFS and labour measures"),
         _mod("Agricultural Statistics", "2h", "lesson", "Land use, crop area and production statistics"),
         _mod("Estimation & Dissemination", "1.5h", "lab", "Estimate employment indicators from sample data"),
     ])),
    ("course-6", "NSSTA-TPAC-206", "SDG Indicators and Metadata", "NSSTA",
     "SDG indicator framework, national baselines, metadata standards and reporting.",
     json.dumps(["SDG Indicators", "Metadata Standards", "Data Quality"]), "Beginner", "4 weeks", "English", 4.5, "🌍", "Statistical",
     json.dumps([
         _mod("SDG Indicator Framework", "2h", "lesson", "Global indicator framework and tiers"),
         _mod("Metadata & Data Reporting", "1.5h", "lesson", "Reporting mechanisms, metadata standards"),
         _mod("SDG Data Exercise", "1h", "lab", "Populate indicators for sample districts"),
     ])),
    ("course-7", "iGOT-MOD-301", "Python for Government Data Analysis", "iGOT Karmayogi",
     "Learn Python programming tailored for government data analysis: pandas, numpy, data cleaning and automated reporting.",
     json.dumps(["Python", "Data Visualization", "Data Quality"]), "Beginner", "10 weeks", "English", 4.6, "🐍", "Technical",
     json.dumps([
         _mod("Python Basics", "2h", "lesson", "Variables, data types, control flow", code=PY_BASICS, sandbox="python"),
         _mod("Pandas Fundamentals", "2h", "lab", "DataFrames, filtering and aggregation", code=PY_PANDAS, sandbox="python"),
         _mod("Data Cleaning with pandas", "2h", "lab", "Missing values, types, deduplication", code=PY_CLEAN, sandbox="python"),
         _mod("Automated Reporting", "1.5h", "lab", "Batch report generation for NSSO data", code=PY_REPORT, sandbox="python"),
         _mod("Python Assessment", "30m", "quiz", "Data analysis quiz in Python"),
     ])),
    ("course-8", "iGOT-MOD-302", "SQL for Statistical Databases", "iGOT Karmayogi",
     "Master SQL for managing and querying statistical databases - joins, aggregations and design patterns.",
     json.dumps(["SQL", "Data Quality"]), "Intermediate", "6 weeks", "English", 4.4, "🗃️", "Technical",
     json.dumps([
         _mod("SQL Fundamentals", "2h", "lesson", "SELECT, WHERE, filtering and ordering", code=SQL_HIGH, sandbox="sql"),
         _mod("Joins & Aggregations", "2h", "lab", "Joins, GROUP BY, window functions", code=SQL_AGG, sandbox="sql"),
         _mod("Statistical Database Design", "1.5h", "lesson", "Normalization and schema patterns"),
         _mod("SQL Assessment", "30m", "quiz", "Write queries against a statistical schema"),
     ])),
    ("course-9", "iGOT-MOD-303", "Data Visualization with Power BI", "iGOT Karmayogi",
     "Create compelling dashboards and reports with Power BI for government reporting.",
     json.dumps(["Data Visualization", "SQL"]), "Intermediate", "5 weeks", "English", 4.3, "📈", "Technical",
     json.dumps([
         _mod("Visual Design Principles", "1.5h", "lesson", "Choosing the right chart for the message"),
         _mod("Power BI Reports", "2h", "lab", "Build interactive dashboards from survey data"),
         _mod("Dashboard for Policy Makers", "1.5h", "lab", "Storytelling with official statistics"),
     ])),
    ("course-10", "iGOT-MOD-304", "Introduction to Artificial Intelligence", "iGOT Karmayogi",
     "Foundation course on AI concepts, machine learning basics and applications in government.",
     json.dumps(["AI/ML", "Python"]), "Beginner", "8 weeks", "English", 4.8, "🤖", "Technical",
     json.dumps([
         _mod("AI Concepts & Ethics of AI", "2h", "lesson", "AI paradigms and responsible AI principles"),
         _mod("Machine Learning Basics", "2h", "lesson", "Regression, classification, evaluation"),
         _mod("ML Lab", "2h", "lab", "Train a simple classifier on sample data", code=PY_ML, sandbox="python"),
         _mod("AI in Official Statistics", "1.5h", "lesson", "Use cases: predictive analytics, anomaly detection"),
         _mod("AI Assessment", "30m", "quiz", "Check understanding of ML fundamentals"),
     ])),
    ("course-11", "iGOT-MOD-305", "Advanced Machine Learning for Statistics", "iGOT Karmayogi",
     "Apply ML to regression, classification, clustering and time series forecasting for official data.",
     json.dumps(["AI/ML", "Python", "Data Visualization"]), "Advanced", "12 weeks", "English", 4.9, "🧠", "Technical",
     json.dumps([
         _mod("Advanced Regression & Time Series", "3h", "lesson", "Forecasting official time series"),
         _mod("Classification & Clustering", "2h", "lab", "Classification pipelines and clustering census data", code=PY_CLUSTER, sandbox="python"),
         _mod("Model Evaluation & Deployment", "2h", "lesson", "Validation, drift and deployment"),
     ])),
    ("course-12", "NSSTA-TPAC-207", "Data Privacy and Cybersecurity", "NSSTA",
     "DPDP Act, government cybersecurity frameworks and data protection practices.",
     json.dumps(["Data Privacy", "Cybersecurity", "Digital Signatures"]), "Intermediate", "4 weeks", "English", 4.2, "🔒", "Digital Governance",
     json.dumps([
         _mod("DPDP Act Explained", "2h", "lesson", "Key provisions and obligations for data fiduciaries"),
         _mod("Cybersecurity Fundamentals", "2h", "lesson", "Threats, encryption, access control"),
         _mod("Secure Data Handling Lab", "1.5h", "lab", "Incident response and secure handling scenarios"),
     ])),
    ("course-13", "iGOT-MOD-306", "Leadership in Digital Governance", "iGOT Karmayogi",
     "Leadership skills to drive digital transformation in government.",
     json.dumps(["Leadership", "Communication", "Change Management"]), "Advanced", "6 weeks", "English", 4.5, "🏛️", "Behavioural",
     json.dumps([
         _mod("Leading Digital Transformation", "2h", "lesson", "Vision, culture and digital leadership"),
         _mod("Change Management", "2h", "lesson", "Models and execution of change"),
         _mod("Stakeholder Communication", "1.5h", "lab", "Practical communication simulations"),
     ])),
    ("course-14", "NSSTA-TPAC-208", "Effective Communication for Officials", "NSSTA",
     "Professional communication: report writing, presentations, stakeholder engagement and coordination.",
     json.dumps(["Communication", "Ethics"]), "Beginner", "3 weeks", "Hindi", 4.1, "💬", "Behavioural",
     json.dumps([
         _mod("Writing for the Public Service", "1.5h", "lesson", "Official writing, notes and drafting"),
         _mod("Presentations & Meetings", "1.5h", "lab", "Effective presentations and facilitation"),
     ])),
    ("course-15", "iGOT-MOD-307", "R Programming for Statistics", "iGOT Karmayogi",
     "Statistical computing with R: tidyverse, statistical tests, and reproducible reporting.",
     json.dumps(["R", "Data Visualization"]), "Intermediate", "8 weeks", "English", 4.4, "📐", "Technical",
     json.dumps([
         _mod("R Fundamentals", "2h", "lesson", "Vectors, data frames and functions"),
         _mod("Statistical Tests in R", "2h", "lab", "Hypothesis testing and regression in R"),
         _mod("Reproducible Reports", "1.5h", "lab", "R Markdown for official reporting"),
     ])),
    ("course-16", "iGOT-MOD-308", "Cloud Computing and Digital Infrastructure", "iGOT Karmayogi",
     "Cloud platforms, government cloud (Meghraj), modern digital infrastructure and interoperability.",
     json.dumps(["Cloud Computing", "Government Cloud", "Digital Public Infrastructure", "APIs and Open Data"]), "Beginner", "6 weeks", "English", 4.3, "☁️", "Digital Governance",
     json.dumps([
         _mod("Cloud Fundamentals", "2h", "lesson", "IaaS, PaaS, SaaS and security in the cloud"),
         _mod("Government Cloud Meghraj", "1.5h", "lesson", "GI Cloud and empanelment"),
         _mod("APIs & Open Data", "2h", "lab", "Publish and consume government data APIs"),
     ])),
    ("course-17", "NSSTA-TPAC-209", "GIS for Official Statistics", "NSSTA",
     "Geographic information systems, spatial analysis and mapping for official statistics.",
     json.dumps(["GIS", "Data Visualization"]), "Intermediate", "5 weeks", "English", 4.2, "🗺️", "Technical",
     json.dumps([
         _mod("GIS Fundamentals", "2h", "lesson", "Coordinate systems, layers and data models"),
         _mod("Spatial Analysis & Mapping", "2h", "lab", "Choropleth and thematic mapping of district data"),
     ])),
]

# ---------------------------------------------------------------- learner/admin competencies
LEARNER_COMPETENCIES = {
    "survey-design": 3, "sampling": 2, "data-quality": 3,
    "python": 1, "sql": 2, "data-visualization": 2, "ai-ml": 1,
    "cybersecurity": 2, "data-privacy": 3,
    "communication": 4, "leadership": 2, "project-management": 2,
    "national-accounts": 2, "price-statistics": 2, "labour-statistics": 2,
    "agricultural-statistics": 2, "industrial-statistics": 2,
    "sdg-indicators": 3, "metadata-standards": 2,
    "r": 1, "stata": 2, "spss": 2, "sas": 1, "gis": 1,
    "cloud-computing": 1, "api-open-data": 1,
    "digital-signatures": 2, "government-cloud": 1, "digital-public-infra": 1,
    "ethics": 4, "decision-making": 3, "change-management": 2,
}

ADMIN_COMPETENCIES = {cid: 5 for cid in ALL_COMP_IDS}
ADMIN_COMPETENCIES.update({
    "python": 3, "r": 3, "sql": 4, "stata": 4, "spss": 3, "sas": 3,
    "gis": 3, "ai-ml": 3, "cloud-computing": 3, "api-open-data": 3,
    "digital-signatures": 3, "government-cloud": 3, "digital-public-infra": 3,
})

# ---------------------------------------------------------------- labs
LABS = [
    ("lab-python", "Python Data Lab", "Technical",
     "Run Python snippets to explore data analysis fundamentals - variables, lists, loops, dictionaries and basic statistics.",
     "🐍", json.dumps([
         {"title": "Basics", "code": "ages = [28, 34, 29, 41, 36]\nprint('Mean age:', sum(ages) / len(ages))"},
         {"title": "Statistics", "code": "import statistics\nvalues = [3.1, 2.8, 3.6, 3.9, 2.4]\nprint('Mean:', statistics.mean(values))\nprint('Median:', statistics.median(values))\nprint('Variance:', round(statistics.variance(values), 3))"},
     ])),
    ("lab-sql", "SQL Query Lab", "Technical",
     "Write SQL against real World Bank India statistics - SELECT, WHERE, ORDER BY and aggregates, with errors reported instead of silent failure.",
     "🗃️", json.dumps([
         {"table": "districts", "rows": [["id", "name", "state", "population", "literacy"], [1, "Alwar", "Rajasthan", 3674179, 70.7], [2, "Mysuru", "Karnataka", 3054822, 72.6], [3, "Nashik", "Maharashtra", 6109052, 80.9], [4, "Ludhiana", "Punjab", 3498739, 82.2], [5, "Varanasi", "Uttar Pradesh", 3676841, 70.3], [6, "Thrissur", "Kerala", 3121200, 95.1]]},
         {"table": "samples", "rows": [["district_id", "households_surveyed", "dept"], [1, 420, "NSSO"], [2, 515, "Census"], [3, 310, "NSSTA"], [4, 600, "NSSO"], [5, 275, "Census"], [6, 505, "NSSTA"]]},
     ])),
    ("lab-viz", "Data Visualization Lab", "Technical",
     "Build a chart with your own numbers. Try literacy rates by district or competitor skill levels.",
     "📈", json.dumps([
         {"preset": "Literacy by District", "labels": ["Alwar", "Mysuru", "Nashik", "Ludhiana", "Varanasi", "Thrissur"], "values": [70.7, 72.6, 80.9, 82.2, 70.3, 95.1], "type": "bar"},
     ])),
    ("lab-ml", "AI/ML Playground", "Technical",
     "Fit a linear regression to data points and see predicted values - the same math behind forecasting.",
     "🤖", json.dumps([
         {"title": "Linear Regression", "x": [1, 2, 3, 4, 5, 6], "y": [12, 15, 17, 20, 22, 25], "explain": "hours studied -> score prediction"},
     ])),
    ("lab-gis", "GIS Mapping Sandbox", "Technical",
     "Visualize district data as a thematic map. Explore how GIS layers work for official statistics.",
     "🗺️", json.dumps([
         {"preset": "District Data", "points": [["Alwar", 70.7], ["Mysuru", 72.6], ["Nashik", 80.9], ["Ludhiana", 82.2], ["Varanasi", 70.3], ["Thrissur", 95.1]]},
     ])),
]

# ---------------------------------------------------------------- org learners
ORG_LEARNERS = [
    ("Vikram Singh", "Census Division", "Statistical Investigator", 3.1, 2, 5, "Active"),
    ("Priya Patel", "NSSO", "Data Analyst", 2.8, 3, 4, "Active"),
    ("Amit Verma", "DGCIS", "Senior Statistical Officer", 3.9, 1, 7, "Active"),
    ("Sneha Reddy", "Census Division", "Statistical Investigator", 2.2, 5, 2, "Inactive"),
    ("Rahul Gupta", "NSSO", "Data Analyst", 3.5, 2, 6, "Active"),
    ("Deepa Nair", "NSSTA", "Senior Statistical Officer", 4.1, 1, 8, "Active"),
    ("Karthik Menon", "DGCIS", "Statistical Investigator", 2.6, 3, 3, "Active"),
    ("Meera Joshi", "NSSO", "Data Analyst", 3.0, 3, 4, "Active"),
    ("Suresh Kumar", "NSSTA", "Senior Statistical Officer", 3.7, 2, 5, "Active"),
]


# ---------------------------------------------------------------- connection
def _reset_connection(conn) -> None:
    """Return a connection to the pool in a known-clean state.

    psycopg runs with autocommit off, so any statement leaves the connection
    INTRANS. The pool's built-in reset rolls that back but logs a WARNING per
    return ("rolling back returned connection"), which floods the logs on a
    busy API. Rolling back here keeps the behaviour and drops the noise.
    """
    try:
        if conn.info.transaction_status != TransactionStatus.IDLE:
            conn.rollback()
    except Exception:
        # A connection we cannot reset is not safe to reuse; let the pool
        # discard it rather than handing it to the next request.
        raise


def _check_connection(conn) -> bool:
    """Tell the pool whether a reused connection is still usable.

    The contract is *raise*, not return: psycopg-pool's
    `_getconn_with_check_loop` does `try: self._check_connection(conn) /
    except Exception: self._putconn(conn); <loop for another one> /
    else: return conn`. A callback that returns False is ignored and the
    connection is handed out anyway, so a False return here would look correct
    and do nothing.

    Raising instead makes the pool discard the dead session and transparently
    fetch another, which is what turns an intermittent 500 into a request that
    simply succeeds.

    The probe is a bare `SELECT 1` for the cheapest possible round trip.
    """
    try:
        conn.execute("SELECT 1")
    except Exception as exc:
        raise OperationalError("pooled connection failed its liveness check") from exc
    return True


def get_pool() -> ConnectionPool:
    """Build the shared connection pool on first use.

    Lazy so that importing this module — which scripts/export_seed.py does to
    read the reference constants — never requires a reachable database.
    """
    global _pool
    if _pool is None:
        dsn = (os.environ.get("DATABASE_URL") or "").strip()
        if not dsn:
            raise DatabaseNotConfigured(
                "DATABASE_URL is not set. Copy .env.example to backend/.env and fill in "
                "the Supabase session-pooler connection string, then restart the backend."
            )
        # Without a connect timeout, a blackholed database host (firewall DROP
        # rather than REJECT) leaves the TCP handshake pending forever. The
        # request thread never returns, so a single bad packet-either-drops the
        # worker instead of producing a 500 the load balancer can route around.
        # An unreachable DB should be a fast, visible error.
        connect_timeout = _positive_int("DB_CONNECT_TIMEOUT_SECONDS", 10)
        pool_max = _positive_int("DB_POOL_MAX", 10)
        _pool = ConnectionPool(
            dsn,
            min_size=1,
            max_size=pool_max,
            open=False,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": connect_timeout,
            },
            reset=_reset_connection,
            # A pooled connection that the *server* has closed is still handed
            # back out by the pool, because the pool cannot tell the difference
            # between "idle" and "idle to a server that dropped it". Supabase's
            # pooler reaps idle sessions, so on a service that sits quiet between
            # demo sessions the next request checks out a dead socket and fails
            # with `SSL SYSCALL error: Can't assign requested address` -- an
            # intermittent 500 that recovers on retry and reads as a flake.
            # `check` verifies the connection on checkout so a dead one is
            # discarded and replaced instead of being handed to a request.
            check=_check_connection,
            # Bounding the checkout wait matters as much as the TCP timeout: if
            # every pooled connection is busy, getconn() must fail fast rather
            # than pile up request threads waiting for a free slot.
            timeout=connect_timeout,
        )
        _pool.open()
    return _pool


def _positive_int(name: str, default: int) -> int:
    """Read a positive integer from the environment, or fail with the name.

    A raw ``int()`` here raises ``ValueError: invalid literal for int()`` from
    inside a request handler, which tells whoever is on call nothing about which
    variable is wrong. A misconfigured pool size should be a startup-shaped
    error, not a mystery 500.
    """
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(
            f"{name} must be a whole number, got {raw!r}. "
            f"Remove it to use the default of {default}."
        ) from None
    if value < 1:
        raise RuntimeError(
            f"{name} must be at least 1, got {value}. "
            f"Remove it to use the default of {default}."
        )
    return value


class _PooledConnection:
    """Adapter whose ``close()`` returns the connection to the pool.

    ``psycopg-pool``'s ``getconn()`` hands back a plain ``psycopg.Connection``
    that has no idea a pool exists. Calling ``.close()`` on it therefore closes
    the real socket *without* telling the pool, and the pool keeps counting that
    slot as checked out forever. The connection is gone, but the slot is not,
    so it is never reused.

    That is a silent, total outage rather than a slow leak: the pool fills to
    ``max_size`` after a few dozen requests and every later request blocks for
    30s and then raises ``PoolTimeout``. Every router here calls
    ``conn.close()`` in a ``finally``, so the entire API stops working.

    Verified on both psycopg-pool 3.2.3 and 3.3.3 — both return a plain
    ``Connection`` from ``getconn()``, so neither is safe to call ``.close()``
    on directly. ``putconn()`` is the documented way to hand a connection back
    and exists in both, so use it unconditionally.
    """

    __slots__ = ("_pool", "_conn", "_used")

    def __init__(self, pool: ConnectionPool, conn) -> None:
        self._pool = pool
        self._conn = conn
        # Has any statement been sent on this connection yet? A connection that
        # dies before its first statement provably executed nothing, which is
        # what makes the retry in execute() safe.
        self._used = False

    def __getattr__(self, name):
        # execute / commit / rollback / fetchall / row_factory all pass through.
        return getattr(self._conn, name)

    def execute(self, query, *args, **kwargs):
        """Run a statement, replacing the connection once if it is already dead.

        Supabase's pooler reaps idle sessions, so a slot can be handed back
        holding a socket the server has since closed. psycopg reports that as
        `OperationalError: the connection is closed`, and without this the
        caller sees a 500 on the first request after an idle spell -- a
        failure that then clears on its own, which is what makes it read as a
        mysterious flake rather than a bug.

        The retry is deliberately narrow, because a blanket "retry on
        OperationalError" is unsafe: for a write, the connection can drop
        *after* the server has already applied the statement, and replaying it
        would double-apply. Here the retry only fires when this adapter has
        not yet sent a single statement, so nothing can have been applied and a
        fresh connection running it for the first time is guaranteed correct.

        A second failure propagates: if a brand-new connection cannot execute
        the query, the database is genuinely unavailable and the caller should
        see that as a 500.
        """
        try:
            result = self._conn.execute(query, *args, **kwargs)
        except OperationalError:
            if self._used:
                # A statement already went out on this connection, so its fate
                # is unknown. Replaying it could duplicate a write.
                raise
            try:
                # putconn(), not close(): close() on the raw connection would
                # drop the socket while the pool still counts the slot as
                # checked out, leaking it until the pool starves (see
                # _PooledConnection's docstring). Returning it lets the pool's
                # own `check` callback see the dead connection and discard it.
                self._pool.putconn(self._conn)
            except Exception:
                pass
            self._conn = self._pool.getconn()
            result = self._conn.execute(query, *args, **kwargs)
        self._used = True
        return result

    def close(self) -> None:
        # Roll back first. autocommit is off, so any statement leaves the
        # connection INTRANS, and psycopg-pool logs a WARNING for every
        # connection returned that way ("rolling back returned connection"),
        # which floods the logs on a busy API. Cleaning up here means the pool
        # always sees an IDLE connection. Read handlers never commit, so this
        # only ever discards a read-only transaction.
        try:
            if self._conn.info.transaction_status != TransactionStatus.IDLE:
                self._conn.rollback()
        except Exception:
            pass
        try:
            self._pool.putconn(self._conn)
        except Exception:
            # Never let cleanup mask the caller's own exception.
            try:
                self._conn.close()
            except Exception:
                pass


def get_db_connection():
    """Return a pooled connection for the usual execute/commit/close pattern.

    ``.close()`` returns the connection to the pool rather than tearing it down,
    which is why every router's try/finally + close() keeps working unchanged.
    See ``_PooledConnection`` for why that distinction needs an adapter.

    psycopg runs with autocommit off, so a bare SELECT opens a transaction that
    close() rolls back — harmless for reads — and an explicit conn.commit()
    still gives routers the atomic block they expect.

    This must be `getconn()`, not `connection()`. `connection()` is a
    @contextmanager generator: calling it hands back a
    _GeneratorContextManager, which has no execute/commit/close, so every
    caller raised AttributeError before reaching the database. `getconn()`
    checks a connection out of the pool.
    """
    pool = get_pool()
    return _PooledConnection(pool, pool.getconn())


def close_pool() -> None:
    """Close the pool. Used by tests; harmless to call when never opened."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _has_auth_schema(conn) -> bool:
    row = conn.execute(
        "SELECT 1 AS ok FROM information_schema.schemata WHERE schema_name = 'auth'"
    ).fetchone()
    return bool(row)


# ---------------------------------------------------------------- migrations
def _applied_migrations(conn) -> set[str]:
    # seed_meta is created by 001, but it does not exist yet on a virgin
    # database, so make sure it does before asking what has been applied.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS seed_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    row = conn.execute("SELECT value FROM seed_meta WHERE key = 'migrations'").fetchone()
    return {part for part in (row or {}).get("value", "").split(",") if part}


def _record_migration(conn, name: str, applied: set[str]) -> None:
    applied.add(name)
    conn.execute(
        "INSERT INTO seed_meta (key, value) VALUES ('migrations', %s) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (",".join(sorted(applied)),),
    )


def _run_migration_file(conn, path: Path) -> None:
    """Execute one .sql file inside the caller's transaction.

    The migration files carry their own BEGIN/COMMIT so they can also be
    pasted straight into the Supabase SQL editor. psycopg already wraps this
    call in a transaction and nesting one is an error, so those two outer
    markers are stripped before execution.
    """
    sql = path.read_text(encoding="utf-8")
    for marker in ("BEGIN;", "COMMIT;"):
        sql = sql.replace(marker, "")
    conn.execute(sql)


def apply_migrations() -> list[str]:
    """Apply migration files not yet recorded in seed_meta.

    Idempotent — already-applied files are skipped, so this is one cheap query
    on a warm start. Returns the names applied during this call.
    """
    if not MIGRATIONS_DIR.is_dir():
        raise DatabaseNotConfigured(
            f"migrations directory not found at {MIGRATIONS_DIR}. Run the backend from "
            "the repo checkout, or apply supabase/migrations/*.sql via the Supabase SQL "
            "editor and insert the filenames into seed_meta under key 'migrations'."
        )

    conn = get_db_connection()
    applied: set[str] = set()
    newly: list[str] = []
    try:
        applied = _applied_migrations(conn)
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            # 002_rls.sql needs Supabase's `auth` schema. On a plain PostgreSQL
            # instance (CI, local dev) skip it instead of failing the boot —
            # those policies are documented as correct-but-inactive for the
            # backend anyway, since it connects as the table owner.
            if path.name.endswith("_rls.sql") and not _has_auth_schema(conn):
                print(f"[db] skipping {path.name}: no `auth` schema (not a Supabase project)")
                continue
            _run_migration_file(conn, path)
            _record_migration(conn, path.name, applied)
            newly.append(path.name)
            print(f"[db] applied {path.name}")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return newly


def init_db() -> None:
    """Startup hook called from the FastAPI lifespan.

    Applies any pending migrations (which includes the one-time seed). The old
    SQLite version re-inserted reference data on every boot, which is why it
    needed such careful "INSERT OR IGNORE" discipline; recording applied
    migrations removes the whole class of problem.
    """
    apply_migrations()


def healthcheck() -> dict:
    """Probe the database for the /api/health endpoint.

    Reports what it actually knows rather than asserting a cause. A paused
    free Supabase project refuses connections, and the driver's message for
    that is indistinguishable from a bad host or a dropped network — so
    `hint` offers the most likely fix without claiming it is the cause.

    Security: this endpoint is unauthenticated, and the driver exception
    string embeds the connection host, port and username. psycopg masks the
    password, but `aws-0-<region>.pooler.supabase.com` and `postgres.<ref>`
    are still infrastructure detail worth not publishing. So `detail` stays
    generic and only the exception *class name* is exposed in `error_type`.
    The full text goes to the server log instead.
    """
    result: dict = {
        "status": "error",
        "service": "sakshamai-backend",
        "database": "unreachable",
        "detail": "",
        "hint": "",
        "error_type": "",
    }
    try:
        conn = get_db_connection()
    except DatabaseNotConfigured as exc:
        result["detail"] = str(exc)
        result["hint"] = "Copy .env.example to backend/.env and set DATABASE_URL."
        return result
    except Exception as exc:  # pool could not even open
        logger.warning("%s", safe_exception(exc, context="database pool unavailable"))
        result["detail"] = "connection pool unavailable"
        result["error_type"] = type(exc).__name__
        result["hint"] = (
            "If this project has never been used recently it may be paused: open "
            "the Supabase dashboard and choose Restore project, then retry. "
            "Free projects pause after a period of inactivity; Pro does not."
        )
        return result

    try:
        conn.execute("SELECT 1 AS ok").fetchone()
        result["database"] = "ok"
        result["status"] = "ok"
        row = conn.execute("SELECT value FROM seed_meta WHERE key = 'version'").fetchone()
        result["seedVersion"] = (row or {}).get("value")
        result["hint"] = (
            "Migrations are not applied yet." if not row else ""
        )
    except Exception as exc:
        # Same reasoning as above: the driver text can name the host, port and
        # user, and this route is public. Class name only, full text to the log.
        logger.warning("%s", safe_exception(exc, context="database health query failed"))
        result["detail"] = "database query failed"
        result["error_type"] = type(exc).__name__
        result["hint"] = (
            "If this project has never been used recently it may be paused: open "
            "the Supabase dashboard and choose Restore project, then retry."
        )
    finally:
        conn.close()
    return result
