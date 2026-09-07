"""SQLite database setup, schema, and seed data for SakshamAI."""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent / "sakshamai.db"

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
     "Query a real district-level census dataset with SELECT, WHERE, GROUP BY and JOIN.",
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


def _columns(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_db_connection()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        employee_id TEXT,
        designation TEXT,
        department TEXT,
        role TEXT NOT NULL DEFAULT 'learner',
        current_role TEXT,
        education TEXT,
        experience INTEGER DEFAULT 0,
        career_goal TEXT,
        previous_training TEXT,
        preferred_language TEXT DEFAULT 'English',
        profile_completed INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS competencies (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT
    );

    CREATE TABLE IF NOT EXISTS competency_scores (
        user_id TEXT NOT NULL,
        competency_id TEXT NOT NULL,
        level INTEGER NOT NULL,
        PRIMARY KEY (user_id, competency_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (competency_id) REFERENCES competencies(id)
    );

    CREATE TABLE IF NOT EXISTS role_requirements (
        role TEXT NOT NULL,
        competency_id TEXT NOT NULL,
        level INTEGER NOT NULL,
        PRIMARY KEY (role, competency_id)
    );

    CREATE TABLE IF NOT EXISTS courses (
        id TEXT PRIMARY KEY,
        course_code TEXT,
        title TEXT NOT NULL,
        provider TEXT NOT NULL,
        description TEXT,
        skills_covered TEXT NOT NULL,
        difficulty TEXT,
        duration TEXT,
        language TEXT,
        rating REAL DEFAULT 0,
        thumbnail TEXT,
        category TEXT,
        modules TEXT NOT NULL DEFAULT '[]'
    );

    CREATE TABLE IF NOT EXISTS course_enrollments (
        user_id TEXT NOT NULL,
        course_id TEXT NOT NULL,
        progress INTEGER DEFAULT 0,
        enrolled_at TEXT DEFAULT CURRENT_DATE,
        PRIMARY KEY (user_id, course_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (course_id) REFERENCES courses(id)
    );

    CREATE TABLE IF NOT EXISTS module_progress (
        user_id TEXT NOT NULL,
        course_id TEXT NOT NULL,
        module_title TEXT,
        completed_at TEXT DEFAULT CURRENT_DATE,
        PRIMARY KEY (user_id, course_id, module_title)
    );

    CREATE TABLE IF NOT EXISTS quizzes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT,
        date TEXT DEFAULT CURRENT_DATE,
        score INTEGER DEFAULT 0,
        total_questions INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS quiz_questions (
        id TEXT PRIMARY KEY,
        quiz_id TEXT NOT NULL,
        question TEXT,
        options TEXT NOT NULL,
        correct_answer INTEGER NOT NULL,
        user_answer INTEGER,
        explanation TEXT,
        difficulty TEXT,
        source_excerpt TEXT,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        message TEXT,
        type TEXT DEFAULT 'info',
        date TEXT,
        is_read INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS activities (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        action TEXT,
        detail TEXT,
        date TEXT,
        icon TEXT
    );

    CREATE TABLE IF NOT EXISTS labs (
        id TEXT PRIMARY KEY,
        title TEXT,
        category TEXT,
        description TEXT,
        icon TEXT,
        exercises TEXT
    );

    CREATE TABLE IF NOT EXISTS org_learners (
        name TEXT PRIMARY KEY, department TEXT, job_role TEXT,
        competency REAL, gaps INTEGER, completed INTEGER, status TEXT
    );
    """)

    # --- migrations for older DB files ------------------------------------
    course_cols = _columns(conn, "courses")
    if "course_code" not in course_cols:
        cur.execute("ALTER TABLE courses ADD COLUMN course_code TEXT")
    if "modules" not in course_cols:
        cur.execute("ALTER TABLE courses ADD COLUMN modules TEXT NOT NULL DEFAULT '[]'")

    # --- clear dependent tables in FK-safe order so re-seeding is idempotent
    #     (init_db runs on every startup, including --reload reloads)
    cur.execute("DELETE FROM module_progress")
    cur.execute("DELETE FROM course_enrollments")
    cur.execute("DELETE FROM quiz_questions")
    cur.execute("DELETE FROM quizzes")
    cur.execute("DELETE FROM competency_scores")
    cur.execute("DELETE FROM role_requirements")
    cur.execute("DELETE FROM competencies")
    cur.execute("DELETE FROM courses")
    cur.execute("DELETE FROM labs")

    # --- seed competencies -------------------------------------------------
    cur.executemany(
        "INSERT INTO competencies (id, name, category, description) VALUES (?, ?, ?, ?)",
        COMPETENCIES,
    )

    # --- seed role requirements -------------------------------------------
    cur.executemany(
        "INSERT INTO role_requirements (role, competency_id, level) VALUES (?, ?, ?)",
        ROLE_REQUIREMENTS,
    )

    # --- seed courses ------------------------------------------------------
    cur.executemany(
        "INSERT INTO courses (id, course_code, title, provider, description, skills_covered, difficulty, duration, language, rating, thumbnail, category, modules) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        COURSES,
    )

    # --- seed labs ---------------------------------------------------------
    cur.executemany(
        "INSERT INTO labs (id, title, category, description, icon, exercises) VALUES (?, ?, ?, ?, ?, ?)",
        LABS,
    )

    # --- seed users ---------------------------------------------------------
    if not cur.execute("SELECT id FROM users WHERE id = 'learner-1'").fetchone():
        cur.execute(
            "INSERT INTO users (id, name, employee_id, designation, department, role, current_role, education, experience, career_goal, previous_training, preferred_language, profile_completed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("learner-1", "Ananya Sharma", "GOV-2021-0847", "Statistical Investigator",
             "National Sample Survey Office", "learner", "Data Analyst", "M.Sc. Statistics, University of Delhi",
             3, "Senior Statistical Officer", "Basic Data Entry, Census Operations Training", "English", 1),
        )
    cur.execute("DELETE FROM competency_scores WHERE user_id = 'learner-1'")
    for cid, lvl in LEARNER_COMPETENCIES.items():
        cur.execute(
            "INSERT INTO competency_scores (user_id, competency_id, level) VALUES (?, ?, ?)",
            ("learner-1", cid, lvl),
        )

    if not cur.execute("SELECT id FROM users WHERE id = 'admin-1'").fetchone():
        cur.execute(
            "INSERT INTO users (id, name, employee_id, designation, department, role, current_role, education, experience, career_goal, previous_training, preferred_language, profile_completed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("admin-1", "Dr. Rajesh Kumar", "GOV-2015-0123", "Director",
             "National Sample Survey Office", "admin", "Administrator", "Ph.D. Statistics, IIT Kanpur",
             15, "Additional Secretary", "Leadership Development Program", "English", 1),
        )
    cur.execute("DELETE FROM competency_scores WHERE user_id = 'admin-1'")
    for cid, lvl in ADMIN_COMPETENCIES.items():
        cur.execute(
            "INSERT INTO competency_scores (user_id, competency_id, level) VALUES (?, ?, ?)",
            ("admin-1", cid, lvl),
        )

    # --- notifications & activities -----------------------------------------
    if not cur.execute("SELECT id FROM notifications WHERE user_id = 'learner-1'").fetchone():
        notifications = [
            ("n1", "learner-1", "Your Data Visualization competency improved from Level 2 to Level 3 after completing the recommended course and assessment.", "success", "2025-09-01", 0),
            ("n2", "learner-1", "New course available: Advanced Machine Learning for Statistics", "info", "2025-08-28", 0),
            ("n3", "learner-1", "You have multiple high-priority skill gaps to address for your target role.", "warning", "2025-08-25", 1),
            ("n4", "learner-1", "Monthly learning streak: 7 days! Keep it up.", "success", "2025-08-20", 1),
        ]
        cur.executemany(
            "INSERT INTO notifications (id, user_id, message, type, date, is_read) VALUES (?, ?, ?, ?, ?, ?)",
            notifications,
        )

    if not cur.execute("SELECT id FROM activities WHERE user_id = 'learner-1'").fetchone():
        activities = [
            ("a1", "learner-1", "Completed Quiz", "Python for Government Data Analysis - Score: 80%", "2025-09-01", "📝"),
            ("a2", "learner-1", "Enrolled in Course", "Data Visualization with Power BI", "2025-08-28", "📚"),
            ("a3", "learner-1", "Skill Improved", "Data Visualization: Level 2 → Level 3", "2025-08-25", "🎯"),
            ("a4", "learner-1", "Completed Course", "Introduction to Artificial Intelligence", "2025-08-20", "✅"),
            ("a5", "learner-1", "Profile Updated", "Added career goal: Senior Statistical Officer", "2025-08-15", "👤"),
        ]
        cur.executemany(
            "INSERT INTO activities (id, user_id, action, detail, date, icon) VALUES (?, ?, ?, ?, ?, ?)",
            activities,
        )

    # --- org learners -------------------------------------------------------
    if not cur.execute("SELECT name FROM org_learners").fetchone():
        cur.executemany(
            "INSERT INTO org_learners VALUES (?, ?, ?, ?, ?, ?, ?)",
            ORG_LEARNERS,
        )

    conn.commit()
    conn.close()