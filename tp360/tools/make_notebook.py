"""Writes tp360/setup_tp360.ipynb (keeps the notebook source reviewable as Python)."""
import json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
cells = []
md = lambda s: cells.append(dict(cell_type="markdown", metadata={}, source=s.strip("\n")))
code = lambda s: cells.append(dict(cell_type="code", metadata={}, execution_count=None, outputs=[], source=s.strip("\n")))

md("""
# Taxpayer 360 + Return Viewer Editor POC — setup

Run top to bottom (**Run all**) on Serverless. It:

1. Creates the schema and a `raw` volume
2. Copies `tp360/data/*.csv` into the volume and loads one Delta table per CSV
3. Runs `sql/tp360_views.sql` — the signals, the TP360 header, the RVE three-column view, related parties, timeline
4. **Validates** (stops on failure): every signal matches the Python answer key, and the two hero exams compute to
   the expected deficiencies ($2,417 and $11,000)
5. Shows the two hero cases
6. Optional: GraphFrames motif search on the relationship graph (skipped cleanly if GraphFrames is not available)
7. Writes the Genie benchmark SQL with your catalog and schema filled in

Fictional taxpayers, synthetic data, no FTI. Table names are POC names, not CDW names.
""")
code("""
dbutils.widgets.text("catalog", "workspace", "1. Catalog")
dbutils.widgets.text("schema", "tp360_poc", "2. Schema")
dbutils.widgets.text("data_dir", "./data", "3. CSV folder (kit path or /Volumes/...)")
dbutils.widgets.text("views_sql", "./sql/tp360_views.sql", "4. Views SQL file")
dbutils.widgets.text("benchmark_sql", "./genie/genie_benchmark_answers.sql", "5. Benchmark SQL template")

import os, re, shutil

CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
for name, val in [("catalog", CATALOG), ("schema", SCHEMA)]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", val):
        raise ValueError(f"{name} '{val}' must be letters, digits and underscores only")
FQ = f"`{CATALOG}`.`{SCHEMA}`"
VOLUME_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

def resolve(w):
    p = dbutils.widgets.get(w).strip()
    return p if p.startswith("/") else os.path.abspath(p)

DATA_DIR, VIEWS_SQL, BENCH_SQL = resolve("data_dir"), resolve("views_sql"), resolve("benchmark_sql")
print(FQ, DATA_DIR, VIEWS_SQL, sep="\\n")
""")
md("## 1. Schema, volume and CSVs")
code("""
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {FQ}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {FQ}.`raw`")
csvs = sorted(f for f in os.listdir(DATA_DIR) if f.lower().endswith(".csv"))
if not csvs:
    raise FileNotFoundError(f"No .csv files in {DATA_DIR}")
if os.path.abspath(DATA_DIR) != os.path.abspath(VOLUME_DIR):
    for f in csvs:
        shutil.copyfile(os.path.join(DATA_DIR, f), os.path.join(VOLUME_DIR, f))
print(f"{len(csvs)} CSVs in {VOLUME_DIR}")
""")
md("## 2. Load one table per CSV")
code("""
for f in csvs:
    t = f[:-4]
    spark.sql(f\"\"\"
        CREATE OR REPLACE TABLE {FQ}.`{t}` AS
        SELECT * FROM read_files('{VOLUME_DIR}/{f}', format => 'csv', header => true, inferSchema => true)
    \"\"\")
    print(f"loaded {t:<28} {spark.table(f'{FQ}.`{t}`').count():>6} rows")
""")
md("## 3. Build the views")
code("""
spark.sql(f"USE CATALOG `{CATALOG}`")
spark.sql(f"USE SCHEMA `{SCHEMA}`")
text = open(VIEWS_SQL).read()
text = "\\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))
for i, st in enumerate([s.strip() for s in re.split(r";\\s*(?:\\n|$)", text) if s.strip()], 1):
    try:
        spark.sql(st)
    except Exception as e:
        raise RuntimeError(f"Statement {i} failed ({' '.join(st.split()[:6])} ...): {e}") from None
    print(f"ok {i:>2}  {' '.join(st.split()[:6])}")
""")
md("## 4. Validate (stops on failure)")
code("""
mm = spark.sql(\"\"\"
  SELECT 'MISSED' AS issue, k.tin_token, k.signal_id FROM tp_signal_answer_key k
  LEFT ANTI JOIN (SELECT DISTINCT tin_token, signal_id FROM v_tp_signals) s USING (tin_token, signal_id)
  UNION ALL
  SELECT 'EXTRA', s.tin_token, s.signal_id FROM (SELECT DISTINCT tin_token, signal_id FROM v_tp_signals) s
  LEFT ANTI JOIN tp_signal_answer_key k USING (tin_token, signal_id)
\"\"\")
n_mm = mm.count()
defs = {r["tin_token"]: r["deficiency"] for r in spark.sql("SELECT tin_token, deficiency FROM v_exam_results").collect()}
print("signal mismatches:", n_mm)
print("deficiencies:", defs)
display(spark.sql("SELECT signal_id, count(DISTINCT tin_token) AS taxpayers FROM v_tp_signals GROUP BY signal_id ORDER BY signal_id"))
if n_mm:
    display(mm)
if n_mm or defs.get("TK100001") != 2417 or defs.get("TK200001") != 11000:
    raise RuntimeError("VALIDATION FAILED")
print("VALIDATION PASSED")
""")
md("""
## 5. The two hero cases

**Case A — Marisol T. Vance:** the TP360 collection taxpayer, and her TY2024 return through RVE.
**Case B — Marcus and Elena Thornbury:** TY2024 exam on a real estate professional claim.
""")
code("""
display(spark.sql("SELECT * FROM v_tp360_header WHERE case_group IN ('HERO_A','HERO_B') AND entity_type = 'INDIVIDUAL'"))
display(spark.sql("SELECT * FROM v_tp_signals WHERE tin_token IN ('TK100001','TK200001') ORDER BY tin_token, signal_id"))
""")
code("""
# The three-column view: as filed, as adjusted, delta — only the lines that changed
display(spark.sql(\"\"\"
  SELECT tin_token, form, line, sub_id, line_desc, as_filed, as_adjusted, delta, data_origin
  FROM v_return_compare WHERE tin_token IN ('TK100001','TK200001') AND delta <> 0
  ORDER BY tin_token, CASE WHEN form = '1040' THEN 2 ELSE 1 END, form, line\"\"\"))
""")
code("""
# Reconciliation findings by branch: A resolved from data, B not a taxpayer issue, C needs the taxpayer (IDR)
display(spark.sql("SELECT tin_token, finding_id, branch, disposition, item, irp_amount, return_ref, return_amount, note FROM tp_rri_finding WHERE tin_token IN ('TK100001','TK200001') ORDER BY tin_token, finding_id"))
""")
md("""
## 6. Optional — graph with GraphFrames

GraphFrames ships with Databricks Runtime for Machine Learning. On Serverless or Free Edition it may not be
available; this cell then says so and you use `v_related_parties_named` (the SQL two-hop view) instead.
The motif finds three-hop chains such as Marisol → Latimer Grove ← R. Latimer → Harborline.
""")
code("""
try:
    from graphframes import GraphFrame
    v = spark.sql(\"\"\"SELECT tin_token AS id, display_name AS name, entity_type AS kind FROM tp_taxpayer
                       UNION ALL SELECT asset_id, description, asset_type FROM tp_asset\"\"\")
    e = spark.sql("SELECT from_id AS src, to_id AS dst, rel_type FROM tp_relationship")
    g = GraphFrame(v, e)
    chains = g.find("(a)-[e1]->(b); (c)-[e2]->(b); (c)-[e3]->(d)").filter(
        "a.id = 'TK100001' AND c.id <> a.id AND e3.rel_type = 'RESPONSIBLE_PERSON'")
    display(chains.selectExpr("a.name AS taxpayer", "e1.rel_type AS r1", "b.name AS shared_entity",
                              "c.name AS co_party", "e3.rel_type AS r3", "d.name AS reaches"))
    spark.sparkContext.setCheckpointDir(f"/Volumes/{CATALOG}/{SCHEMA}/raw/_gf_checkpoint")
    cc = g.connectedComponents()
    display(cc.groupBy("component").count().orderBy("count", ascending=False).limit(10))
except Exception as ex:
    print("GraphFrames not available here — use v_related_parties_named instead.")
    print(type(ex).__name__, str(ex)[:200])
    display(spark.sql("SELECT related_name, hops, path, via_name, related_signals FROM v_related_parties_named WHERE tin_token = 'TK100001' ORDER BY hops"))
""")
md("## 7. Genie benchmark SQL for this catalog and schema")
code("""
bench = open(BENCH_SQL).read().replace("{{catalog}}", CATALOG).replace("{{schema}}", SCHEMA)
out = f"{VOLUME_DIR}/genie_benchmark_answers_{CATALOG}_{SCHEMA}.sql"
with open(out, "w") as fh:
    fh.write(bench)
print("wrote", out)
print(\"\"\"Genie space tables: v_tp360_header, v_tp_signals, v_return_compare, v_exam_results, v_related_parties_named,
v_tp_timeline, tp_taxpayer, tp_tax_module, tp_compliance_episode, tp_rri_finding, tp_idr, tp_adjustment,
tp_return_snapshot, tp_return_line, tp_bank_account, tp_transfer, tp_information_return
(never tp_signal_answer_key)\"\"\")
""")

nb = dict(cells=cells, metadata={"language_info": {"name": "python"},
                                 "application/vnd.databricks.v1+notebook": {"language": "python", "notebookName": "setup_tp360"}},
          nbformat=4, nbformat_minor=5)
for c in nb["cells"]:
    c["source"] = c["source"].splitlines(keepends=True)
with open(os.path.join(ROOT, "setup_tp360.ipynb"), "w") as fh:
    json.dump(nb, fh, indent=1)
print("wrote setup_tp360.ipynb")
