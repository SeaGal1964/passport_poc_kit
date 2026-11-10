"""Writes viewer/Genie_Setup_Helper.html: copy buttons for every Genie example and benchmark (catalog/schema filled)."""
import html, json, os, re, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
cat, sch = (sys.argv[1:3] + ["workspace", "tp360_poc"][len(sys.argv[1:3]):]) if len(sys.argv) > 1 else ("workspace", "tp360_poc")

def parse(path, prefix):
    text = open(os.path.join(ROOT, "genie", path)).read().replace("{{catalog}}", cat).replace("{{schema}}", sch)
    items = []
    for m in re.finditer(rf"^-- ({prefix}\d+)\. (.+?)\n(.*?;)\s*$", text, re.S | re.M):
        items.append(dict(id=m.group(1), q=m.group(2).strip(), sql=m.group(3).strip()))
    return items

ex, bm = parse("genie_example_sql.sql", "E"), parse("genie_benchmark_answers.sql", "Q")
SOURCES = ["v_tp360_header", "v_tp_signals", "v_tp_signal_evidence", "v_return_compare", "v_exam_results", "v_related_parties_named",
           "v_tp_timeline", "v_case_results", "v_line_adjustment_frequency", "v_issue_outcomes", "v_detection_mix",
           "v_variance_root_causes", "v_prior_audit_history", "v_prior_audit_summary", "v_prior_audit_issues", "v_repeat_issues",
           "v_notice_history", "v_notice_summary", "v_issue_to_1040_trace", "tp_taxpayer", "tp_tax_module",
           "tp_compliance_episode", "tp_statutory_clock", "tp_relationship", "tp_case_closure", "tp_issue", "tp_issue_code",
           "tp_rri_finding", "tp_idr", "tp_adjustment", "tp_return_snapshot", "tp_return_line", "tp_bank_account"]
md = open(os.path.join(ROOT, "genie", "genie_instructions.md")).read()
instr = md.split("## What the data is", 1)[1]
instr = "Synthetic data only: every taxpayer is fictional and every TIN is a masked token (TK...). There are no SSNs or EINs in these tables; say so if asked.\n\nWHAT THE DATA IS" + instr
instr = instr.replace("## How to answer", "HOW TO ANSWER").replace("## Hero cases", "HERO CASES").replace("**", "").replace("`", "")
data = json.dumps(dict(ex=ex, bm=bm, src=SOURCES, instr=instr.strip())).replace("</", "<\\/")
page = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Genie setup helper — TP360 + RVE</title><style>
body{{font-family:"Segoe UI",Arial,sans-serif;margin:0;background:#f4f6f9;color:#16202e;font-size:14px}}
header{{background:#0b1f3a;color:#fff;padding:14px 20px;border-bottom:2px solid #38b6db}} header h1{{margin:0;font-size:17px}} header p{{margin:4px 0 0;font-size:12.5px;color:#b9cde3}}
main{{max-width:1000px;margin:0 auto;padding:18px 20px 40px}} h2{{font-size:15px;margin:22px 0 4px}} .how{{color:#5b6b80;margin:0 0 10px;font-size:13px}}
.item{{background:#fff;border:1px solid #dde3ea;border-radius:8px;padding:10px 14px;margin-bottom:10px}}
.item.done{{opacity:.55}} .row{{display:flex;gap:10px;align-items:flex-start}} .id{{font-family:Consolas,monospace;font-weight:700;color:#1d3d6b;min-width:34px}}
.q{{flex:1;font-weight:600}} button{{font:inherit;font-size:12px;border:1px solid #1d3d6b;background:#fff;color:#1d3d6b;border-radius:5px;padding:4px 10px;cursor:pointer;white-space:nowrap}}
button:hover,button:focus-visible{{background:#1d3d6b;color:#fff;outline:none}} button.ok{{background:#2e7d4f;border-color:#2e7d4f;color:#fff}}
details{{margin-top:6px}} summary{{cursor:pointer;color:#5b6b80;font-size:12px}} pre{{background:#f4f6f9;border-radius:6px;padding:8px;overflow-x:auto;font-size:12px;margin:6px 0 0}}
label{{font-size:12px;color:#5b6b80;display:flex;gap:4px;align-items:center}}
</style></head><body><header><h1>Genie setup helper — TP360 + RVE POC</h1><p>Catalog <b>{cat}</b> · schema <b>{sch}</b> · copy each question and SQL into the agent. Tick "done" to keep your place (kept only while this page is open).</p></header>
<main><h2>A. Create the agent (only if rebuilding)</h2><p class="how">Genie Agents → New → choose data sources → catalog <b>{cat}</b>, schema <b>{sch}</b>, tick these {{n}} (never tp_signal_answer_key). Use a pro or serverless SQL warehouse. Name it "TP360 + RVE POC".</p><div class="item"><div id="src" style="font-family:Consolas,monospace;font-size:12.5px;line-height:1.7"></div></div>
<h2>B. Instructions (Configure → Instructions → Text)</h2><p class="how">Replace whatever is there with this, then save.</p><div class="item"><div class="row"><span class="q">General instructions ({{chars}} characters)</span><button id="ci">Copy instructions</button></div><details><summary>Show text</summary><pre id="it"></pre></details></div>
<h2>1. Examples (Configure → Examples → Add → Example query)</h2><p class="how">These teach Genie the patterns. Question in the title, SQL in the query box.</p><div id="ex"></div>
<h2>2. Benchmarks (Benchmarks tab → Add benchmark)</h2><p class="how">Question in the question box, SQL as the answer. Then Run all benchmarks.</p><div id="bm"></div></main>
<script>
const D={data};
function copy(t,b){{const done=()=>{{const o=b.textContent;b.textContent="Copied ✓";b.classList.add("ok");setTimeout(()=>{{b.textContent=o;b.classList.remove("ok")}},1400)}};
 if(navigator.clipboard&&window.isSecureContext){{navigator.clipboard.writeText(t).then(done,()=>fb(t,done))}}else fb(t,done)}}
function fb(t,done){{const a=document.createElement("textarea");a.value=t;document.body.appendChild(a);a.select();try{{document.execCommand("copy");done()}}catch(e){{}}a.remove()}}
function esc(s){{return s.replace(/[&<>]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;"}}[c]))}}
function render(list,el){{document.getElementById(el).innerHTML=list.map((x,i)=>`<div class="item" id="${{el}}${{i}}"><div class="row"><span class="id">${{x.id}}</span><span class="q">${{esc(x.q)}}</span>
<button data-t="q" data-l="${{el}}" data-i="${{i}}">Copy question</button><button data-t="s" data-l="${{el}}" data-i="${{i}}">Copy SQL</button><label><input type="checkbox" data-d="${{el}}${{i}}">done</label></div>
<details><summary>Show SQL</summary><pre>${{esc(x.sql)}}</pre></details></div>`).join("")}}
render(D.ex,"ex");render(D.bm,"bm");
document.getElementById("src").innerHTML=D.src.map(x=>"☐ "+x).join("<br>");
document.getElementById("it").textContent=D.instr;
document.getElementById("ci").onclick=e=>copy(D.instr,e.target);
document.addEventListener("click",e=>{{const b=e.target.closest("button[data-t]");if(!b)return;const x=D[b.dataset.l][+b.dataset.i];copy(b.dataset.t==="q"?x.q:x.sql,b)}});
document.addEventListener("change",e=>{{const c=e.target.closest("[data-d]");if(c)document.getElementById(c.dataset.d).classList.toggle("done",c.checked)}});
</script></body></html>"""
page = page.replace("{n}", str(len(SOURCES))).replace("{chars}", f"{len(instr):,}")
open(os.path.join(ROOT, "viewer", "Genie_Setup_Helper.html"), "w").write(page)
print(f"examples {len(ex)}, benchmarks {len(bm)}")
