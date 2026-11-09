"""Local check of tp360_views.sql with DuckDB (no Databricks needed).

Translates the few Databricks-only functions, loads the CSVs, builds the views, and compares
v_tp_signals with the Python answer key. Exit code 1 on any mismatch.

    pip install duckdb
    python tp360/tools/check_sql_local.py
"""
import os, re, sys
import duckdb

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
con = duckdb.connect()
for f in sorted(os.listdir(os.path.join(ROOT, "data"))):
    if f.endswith(".csv"):
        con.execute(f"CREATE TABLE {f[:-4]} AS SELECT * FROM read_csv_auto('{os.path.join(ROOT, 'data', f)}', header=true)")

sql = open(os.path.join(ROOT, "sql", "tp360_views.sql")).read()
sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
con.execute("CREATE MACRO datediff(a, b) AS date_diff('day', CAST(b AS DATE), CAST(a AS DATE))")
sql = re.sub(r"concat_ws\('; ', collect_list\((.+?)\)\)(\s+AS)", r"string_agg(\1, '; ')\2", sql)
for i, st in enumerate([s for s in re.split(r";\s*\n", sql) if s.strip()], 1):
    try:
        con.execute(st)
    except Exception as e:
        print(f"statement {i} failed: {e}\n{st[:400]}")
        sys.exit(1)

mm = con.execute("""
  SELECT 'MISSED' issue, k.* FROM tp_signal_answer_key k
  WHERE NOT EXISTS (SELECT 1 FROM v_tp_signals s WHERE s.tin_token = k.tin_token AND s.signal_id = k.signal_id)
  UNION ALL
  SELECT DISTINCT 'EXTRA', s.tin_token, s.signal_id FROM v_tp_signals s
  WHERE NOT EXISTS (SELECT 1 FROM tp_signal_answer_key k WHERE s.tin_token = k.tin_token AND s.signal_id = k.signal_id)
""").fetchall()
print("signal mismatches:", len(mm))
for r in mm[:20]:
    print("  ", r)
checks = {
    "A deficiency": con.execute("SELECT deficiency FROM v_exam_results WHERE tin_token='TK100001'").fetchone()[0],
    "B deficiency": con.execute("SELECT deficiency FROM v_exam_results WHERE tin_token='TK200001'").fetchone()[0],
    "A 3-col rows": con.execute("SELECT count(*) FROM v_return_compare WHERE tin_token='TK100001'").fetchone()[0],
    "A changed rows": con.execute("SELECT count(*) FROM v_return_compare WHERE tin_token='TK100001' AND delta<>0").fetchone()[0],
    "B changed rows": con.execute("SELECT count(*) FROM v_return_compare WHERE tin_token='TK200001' AND delta<>0").fetchone()[0],
    "Latimer 2-hop": con.execute("SELECT count(*) FROM v_related_parties_named WHERE tin_token='TK100001' AND hops=2").fetchone()[0],
}
print(checks)
print(con.execute("SELECT form,line,sub_id,line_desc,as_filed,as_adjusted,delta,data_origin FROM v_return_compare WHERE tin_token='TK100001' AND delta<>0 ORDER BY form,line").fetchall())
print(con.execute("SELECT related_name, path, via_name, related_signals FROM v_related_parties_named WHERE tin_token='TK100001' AND hops=2").fetchall())
bench = open(os.path.join(ROOT, "genie", "genie_benchmark_answers.sql")).read().replace("{{catalog}}.{{schema}}.", "")
bench = "\n".join(l for l in bench.splitlines() if not l.strip().startswith("--"))
bench_ok = True
for i, st in enumerate([s for s in re.split(r";\s*\n", bench) if s.strip()], 1):
    try:
        n = len(con.execute(st).fetchall())
        print(f"benchmark Q{i}: {n} rows")
        bench_ok &= n > 0
    except Exception as e:
        print(f"benchmark Q{i} FAILED: {e}")
        bench_ok = False
ok = bench_ok and not mm and checks["A deficiency"] == 2417 and checks["B deficiency"] == 11000
print("LOCAL CHECK PASSED" if ok else "LOCAL CHECK FAILED")
sys.exit(0 if ok else 1)
