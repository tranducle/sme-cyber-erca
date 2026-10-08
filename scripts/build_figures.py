from pathlib import Path
import csv
import json

project = Path(__file__).resolve().parents[2]
draft = project / "7_Manuscript_Draft"
data_dir = draft / "figures_src" / "data"
audit_dir = draft / "figures_audit"
data_dir.mkdir(parents=True, exist_ok=True)
audit_dir.mkdir(parents=True, exist_ok=True)

official = project / "9_Audit/review_pipeline_20261005_G1f_STATS/00_pipeline/official_fit_attempt3_completed"
rescue = project / "5_Experiments_Simulations/TopQ1_Experiment_Rescue_20261006/04_Results"

def rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

trace = []

primary = rows(official / "G1F_OFFICIAL_ERCA_CONTRASTS.csv")
with (data_dir / "fig03_primary_contrasts.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["idx","label","estimate","lower","upper"])
    for idx, r in enumerate(primary, start=1):
        label = r.get("", "")
        value = r.get("estimate", r.get("contrast"))
        w.writerow([idx,label,value,r["CI_L"],r["CI_U"]])
        trace.append({
            "figure_id":"fig03","trace_id":f"fig03_contrast_{label}",
            "source_path":str(official / "G1F_OFFICIAL_ERCA_CONTRASTS.csv"),
            "source_type":"csv","source_locator":f"row {label}; columns estimate, CI_L, CI_U",
            "plotted_entity":label,"raw_value":value,"plotted_value":value,
            "transformation":"copied","unit":"probability difference","status":"traced","notes":"Frozen primary contrast."
        })

cv = rows(official / "G1F_OFFICIAL_CV_REPEATS.csv")
with (data_dir / "fig03_cv_delta.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["repeat","delta_logloss"])
    for r in cv:
        w.writerow([r["repeat_id"],r["delta_logloss"]])
        trace.append({
            "figure_id":"fig03","trace_id":f"fig03_cv_{r['repeat_id']}",
            "source_path":str(official / "G1F_OFFICIAL_CV_REPEATS.csv"),
            "source_type":"csv","source_locator":f"repeat {r['repeat_id']}; column delta_logloss",
            "plotted_entity":f"repeat {r['repeat_id']}","raw_value":r["delta_logloss"],
            "plotted_value":r["delta_logloss"],"transformation":"copied",
            "unit":"log loss difference M6 minus B6","status":"traced","notes":"Negative values favor M6."
        })

rob = []
for r in primary:
    if r.get("") in {"H","D"}:
        pass
pmap = {r.get(""): r for r in primary}
rob.append(("Primary",pmap["H"],pmap["D"],str(official / "G1F_OFFICIAL_ERCA_CONTRASTS.csv")))

e1 = {r["contrast"]:r for r in rows(rescue / "E1_ERCA_CONTRASTS.csv")}
rob.append(("Operational impact",e1["H"],e1["D"],str(rescue / "E1_ERCA_CONTRASTS.csv")))

for r in rows(rescue / "E2_LEAVE_ONE_WAVE_RESULTS.csv"):
    hr={"estimate":r["H"],"CI_L":r["H_CI_L"],"CI_U":r["H_CI_U"]}
    dr={"estimate":r["D"],"CI_L":r["D_CI_L"],"CI_U":r["D_CI_U"]}
    rob.append((f"Omit {r['excluded_year']}",hr,dr,str(rescue / "E2_LEAVE_ONE_WAVE_RESULTS.csv")))

for r in rows(rescue / "E4_E5_ABLATION_RESULTS.csv"):
    short = r["removed"].replace("E_","").replace("P_","").replace("_"," ")
    prefix = "E omit" if r["family"] == "E_leave_one_out" else "P omit"
    hr={"estimate":r["H"],"CI_L":r["H_CI_L"],"CI_U":r["H_CI_U"]}
    dr={"estimate":r["D"],"CI_L":r["D_CI_L"],"CI_U":r["D_CI_U"]}
    rob.append((f"{prefix}: {short}",hr,dr,str(rescue / "E4_E5_ABLATION_RESULTS.csv")))

e3 = {r["contrast"]:r for r in rows(rescue / "E3_GAM_CONTRASTS.csv")}
rob.append(("GAM descriptive",e3["H"],e3["D"],str(rescue / "E3_GAM_CONTRASTS.csv")))

with (data_dir / "fig04_robustness.csv").open("w", newline="", encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["idx","label","H","H_lower","H_upper","D","D_lower","D_upper"])
    for idx,(label,h,d,src) in enumerate(rob,start=1):
        w.writerow([idx,label,h["estimate"],h["CI_L"],h["CI_U"],d["estimate"],d["CI_L"],d["CI_U"]])
        for metric,r in [("H",h),("D",d)]:
            trace.append({
                "figure_id":"fig04","trace_id":f"fig04_{idx}_{metric}",
                "source_path":src,"source_type":"csv","source_locator":f"{label}; {metric} estimate and interval",
                "plotted_entity":f"{label} {metric}","raw_value":r["estimate"],"plotted_value":r["estimate"],
                "transformation":"copied into ordered robustness matrix","unit":"probability difference",
                "status":"traced","notes":"GAM row is descriptive only."
            })

later_wave = rows(rescue / "E6_WAVE_CONTRASTS.csv")
pooled = {r["endpoint"]:r for r in rows(rescue / "E6_P_CRITERION_CONTRASTS.csv")}
with (data_dir / "fig05_later_wave.csv").open("w", newline="", encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["idx","label","estimate","lower","upper"])
    out=[]
    for endpoint in ["material","impact"]:
        for r in later_wave:
            if r["endpoint"] == endpoint:
                out.append((f"{endpoint.title()} {r['year']}",r))
        out.append((f"{endpoint.title()} pooled",pooled[endpoint]))
    for idx,(label,r) in enumerate(out,start=1):
        value = r.get("estimate", r.get("contrast"))
        w.writerow([idx,label,value,r["CI_L"],r["CI_U"]])
        trace.append({
            "figure_id":"fig05","trace_id":f"fig05_later_{idx}",
            "source_path":str(rescue / ("E6_WAVE_CONTRASTS.csv" if "pooled" not in label else "E6_P_CRITERION_CONTRASTS.csv")),
            "source_type":"csv","source_locator":label,
            "plotted_entity":label,"raw_value":value,"plotted_value":value,
            "transformation":"copied","unit":"probability difference","status":"traced","notes":"Later-wave response-capacity contrast."
        })

e8={r["contrast"]:r for r in rows(rescue / "E8_SELECTION_CONTRASTS.csv")}
e6r=rows(rescue / "E6_ROUTING_P_CONTRAST.csv")[0]
routing=[
    ("Earlier, high E",e8["H"]),
    ("Earlier, low E",e8["L"]),
    ("Later waves",e6r)
]
with (data_dir / "fig05_routing.csv").open("w", newline="", encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["idx","label","estimate","lower","upper"])
    for idx,(label,r) in enumerate(routing,start=1):
        w.writerow([idx,label,r["estimate"],r["CI_L"],r["CI_U"]])
        trace.append({
            "figure_id":"fig05","trace_id":f"fig05_routing_{idx}",
            "source_path":str(rescue / ("E8_SELECTION_CONTRASTS.csv" if idx < 3 else "E6_ROUTING_P_CONTRAST.csv")),
            "source_type":"csv","source_locator":label,
            "plotted_entity":label,"raw_value":r["estimate"],"plotted_value":r["estimate"],
            "transformation":"copied","unit":"routing probability difference","status":"traced","notes":"Selection into consequence-analysis sample."
        })

tq1=rows(rescue / "E7_TQ1_RESULTS.csv")
wanted={"TQ1_material":"Material","TQ1_impact":"Impact","TQ1_incident":"Incident"}
csls=[]
for r in tq1:
    if r["model"] in wanted and r["term"] == "P_t":
        csls.append((wanted[r["model"]],r))
with (data_dir / "fig05_csls.csv").open("w", newline="", encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["idx","label","estimate","lower","upper"])
    for idx,(label,r) in enumerate(csls,start=1):
        w.writerow([idx,label,r["estimate"],r["CI_L"],r["CI_U"]])
        trace.append({
            "figure_id":"fig05","trace_id":f"fig05_csls_{idx}",
            "source_path":str(rescue / "E7_TQ1_RESULTS.csv"),
            "source_type":"csv","source_locator":f"model {r['model']}; term P_t",
            "plotted_entity":label,"raw_value":r["estimate"],"plotted_value":r["estimate"],
            "transformation":"copied","unit":"logit coefficient","status":"traced","notes":"Lagged-wave association, not causal effect."
        })

(audit_dir / "RESULT_FIGURE_TRACEABILITY.json").write_text(json.dumps(trace,indent=2),encoding="utf-8")
print(json.dumps({"trace_entries":len(trace),"files":[p.name for p in data_dir.glob("fig*.csv")]},indent=2))
