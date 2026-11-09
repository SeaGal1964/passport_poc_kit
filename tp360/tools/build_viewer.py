"""Injects viewer/scenarios.json into the walkthrough template -> viewer/TP360_RVE_Walkthrough.html"""
import json, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data = json.load(open(os.path.join(ROOT, "viewer", "scenarios.json")))
tpl = open(os.path.join(ROOT, "tools", "walkthrough_template.html")).read()
out = tpl.replace("/*__DATA__*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
open(os.path.join(ROOT, "viewer", "TP360_RVE_Walkthrough.html"), "w").write(out)
print("wrote viewer/TP360_RVE_Walkthrough.html", len(out) // 1024, "KB")
