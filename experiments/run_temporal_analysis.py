from pathlib import Path
import csv
import hashlib
import json
import os
from typing import Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.genmod.cov_struct import Exchangeable
from statsmodels.genmod.families import Binomial, Gaussian

ROOT = Path("/Users/let/Documents/LOCAL-CODING-AGENT-MAC/DO_A_PAPER_UPGRADE")
PAPER = ROOT / "PAPERS/C1_coalignment-maturity-construct"
BASE = PAPER / "5_Experiments_Simulations/TopQ1_Experiment_Rescue_20261006"
INPUT = BASE / "03_Inputs/E7_CSLS_MEDIUM_TRANSITIONS.csv"
RESULTS = BASE / "04_Results"
HASH_MANIFEST = BASE / "00_Q0/Q0_EXECUTION_INPUT_HASHES.csv"
AUTH = "REVIEWER7_ACCEPT_HARSH_PASS_Q0"

REQUIRED_COLUMNS = [
    "LongId", "wave_t", "transition", "wght_t",
    "P_t", "E_t", "incident_t", "material_t", "impact_t",
    "P_next", "incident_next", "material_next", "impact_next",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify_input_hash(path: Path, manifest_path: Optional[Path] = None) -> None:
    if manifest_path is None:
        manifest_path = HASH_MANIFEST
    with manifest_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rel = str(path.relative_to(PAPER))
    matches = [r for r in rows if r["path"] == rel]
    if len(matches) != 1:
        raise RuntimeError(f"INPUT_HASH_MANIFEST_ENTRY_MISSING {rel}")
    observed = sha256_file(path)
    if observed != matches[0]["sha256"]:
        raise RuntimeError(f"INPUT_HASH_MISMATCH {rel}")


def term_rows(result, block, model, n, clusters, status="primary"):
    ci = result.conf_int()
    rows = []
    for term in result.params.index:
        rows.append({
            "block": block,
            "model": model,
            "term": term,
            "estimate": float(result.params[term]),
            "SE": float(result.bse[term]),
            "CI_L": float(ci.loc[term, 0]),
            "CI_U": float(ci.loc[term, 1]),
            "pvalue": float(result.pvalues[term]),
            "n": int(n),
            "clusters": int(clusters),
            "status": status,
        })
    return rows


def term_rows_point_only(result, block, model, n, clusters, status):
    rows = []
    for term in result.params.index:
        rows.append({
            "block": block,
            "model": model,
            "term": term,
            "estimate": float(result.params[term]),
            "SE": np.nan,
            "CI_L": np.nan,
            "CI_U": np.nan,
            "pvalue": np.nan,
            "n": int(n),
            "clusters": int(clusters),
            "status": status,
        })
    return rows


def fit_cluster_logit(formula, data, weights=None):
    kw = {}
    if weights is not None:
        kw["freq_weights"] = np.asarray(weights, float)
    model = smf.glm(formula, data=data, family=sm.families.Binomial(), **kw)
    fit = model.fit(cov_type="cluster", cov_kwds={"groups": data["LongId"]})
    if not np.all(np.isfinite(fit.params)):
        raise RuntimeError("NONFINITE_LOGIT_COEFFICIENT")
    return fit


def fit_cluster_linear(formula, data, weights=None):
    if weights is None:
        model = smf.ols(formula, data=data)
    else:
        model = smf.wls(formula, data=data, weights=np.asarray(weights, float))
    fit = model.fit(cov_type="cluster", cov_kwds={"groups": data["LongId"]})
    if not np.all(np.isfinite(fit.params)):
        raise RuntimeError("NONFINITE_LINEAR_COEFFICIENT")
    return fit


def fit_weighted_logit_point(formula, data, weights):
    model = smf.glm(
        formula,
        data=data,
        family=sm.families.Binomial(),
        freq_weights=np.asarray(weights, float),
    )
    fit = model.fit()
    if not np.all(np.isfinite(fit.params)):
        raise RuntimeError("NONFINITE_WEIGHTED_LOGIT_COEFFICIENT")
    return fit


def fit_weighted_linear_point(formula, data, weights):
    model = smf.wls(formula, data=data, weights=np.asarray(weights, float))
    fit = model.fit()
    if not np.all(np.isfinite(fit.params)):
        raise RuntimeError("NONFINITE_WEIGHTED_LINEAR_COEFFICIENT")
    return fit


def fit_gee_binomial(formula, data):
    model = smf.gee(
        formula,
        groups="LongId",
        data=data,
        family=Binomial(),
        cov_struct=Exchangeable(),
    )
    fit = model.fit()
    if not np.all(np.isfinite(fit.params)):
        raise RuntimeError("NONFINITE_GEE_BINOMIAL")
    return fit


def fit_gee_gaussian(formula, data):
    model = smf.gee(
        formula,
        groups="LongId",
        data=data,
        family=Gaussian(),
        cov_struct=Exchangeable(),
    )
    fit = model.fit()
    if not np.all(np.isfinite(fit.params)):
        raise RuntimeError("NONFINITE_GEE_GAUSSIAN")
    return fit


def endpoint_frame(data, cols):
    q = data.dropna(subset=cols).copy()
    if len(q) == 0:
        raise RuntimeError("EMPTY_ENDPOINT_SAMPLE")
    return q


def run_tq1(data):
    rows = []
    specs = [
        ("TQ1_material", "material_next", "material_t"),
        ("TQ1_impact", "impact_next", "impact_t"),
        ("TQ1_incident", "incident_next", "incident_t"),
    ]
    for model_name, outcome, prior in specs:
        q = endpoint_frame(
            data,
            ["P_t", "E_t", prior, outcome, "wave_t", "LongId"],
        )
        formula = f"{outcome} ~ P_t + E_t + {prior} + C(wave_t)"
        fit = fit_cluster_logit(formula, q)
        rows.extend(term_rows(
            fit, "E7_TQ1", model_name, len(q), q.LongId.nunique(),
            "primary_cluster_robust",
        ))
        if model_name == "TQ1_material":
            gee = fit_gee_binomial(formula, q)
            rows.extend(term_rows(
                gee, "E7_TQ1", "TQ1_material_GEE", len(q),
                q.LongId.nunique(), "sensitivity_GEE_exchangeable",
            ))
            qw = endpoint_frame(q, ["wght_t"])
            wfit = fit_weighted_logit_point(formula, qw, qw.wght_t)
            rows.extend(term_rows_point_only(
                wfit, "E7_TQ1", "TQ1_material_weighted", len(qw),
                qw.LongId.nunique(),
                "sensitivity_cross_sectional_weight_point_only_nonlongitudinal",
            ))
    return pd.DataFrame(rows)


def run_tq2(data):
    rows = []
    specs = [
        ("TQ2_material_feedback", "material_t"),
        ("TQ2_impact_feedback", "impact_t"),
        ("TQ2_incident_feedback", "incident_t"),
    ]
    for model_name, prior in specs:
        q = endpoint_frame(
            data,
            ["P_next", "P_t", "E_t", prior, "wave_t", "LongId"],
        )
        formula = f"P_next ~ {prior} + P_t + E_t + C(wave_t)"
        fit = fit_cluster_linear(formula, q)
        rows.extend(term_rows(
            fit, "E7_TQ2", model_name, len(q), q.LongId.nunique(),
            "primary_cluster_robust",
        ))
        if model_name == "TQ2_material_feedback":
            gee = fit_gee_gaussian(formula, q)
            rows.extend(term_rows(
                gee, "E7_TQ2", "TQ2_material_feedback_GEE", len(q),
                q.LongId.nunique(), "sensitivity_GEE_exchangeable",
            ))
            qw = endpoint_frame(q, ["wght_t"])
            wfit = fit_weighted_linear_point(formula, qw, qw.wght_t)
            rows.extend(term_rows_point_only(
                wfit, "E7_TQ2", "TQ2_material_feedback_weighted", len(qw),
                qw.LongId.nunique(),
                "sensitivity_cross_sectional_weight_point_only_nonlongitudinal",
            ))
    return pd.DataFrame(rows)


def load_e7(path: Optional[Path] = None) -> pd.DataFrame:
    if path is None:
        path = INPUT
    verify_input_hash(path)
    d = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in d.columns]
    if missing:
        raise RuntimeError("E7_SCHEMA_MISSING " + ",".join(missing))
    if len(d) != 441:
        raise RuntimeError("E7_ROW_CONTRACT_CHANGED")
    if d["LongId"].nunique() != 302:
        raise RuntimeError("E7_CLUSTER_CONTRACT_CHANGED")
    if int(d["material_next"].sum()) != 76:
        raise RuntimeError("E7_MATERIAL_EVENT_CONTRACT_CHANGED")
    if int(d["impact_next"].sum()) != 182:
        raise RuntimeError("E7_IMPACT_EVENT_CONTRACT_CHANGED")
    if int(d["incident_next"].sum()) != 356:
        raise RuntimeError("E7_INCIDENT_EVENT_CONTRACT_CHANGED")
    if float(d["P_t"].std(ddof=1)) < 0.10:
        raise RuntimeError("E7_P_VARIANCE_GATE_FAILED")
    if int(d["P_t"].nunique()) < 8:
        raise RuntimeError("E7_P_SUPPORT_GATE_FAILED")
    if float(d["P_t"].value_counts(normalize=True).max()) > 0.60:
        raise RuntimeError("E7_P_POINT_MASS_GATE_FAILED")
    return d


def main():
    if os.environ.get("C1_RESCUE_EXEC_AUTH", "") != AUTH:
        raise RuntimeError("RESCUE_EXECUTION_BLOCKED_BY_REVIEW_GATE")
    RESULTS.mkdir(parents=True, exist_ok=True)
    d = load_e7()
    tq1 = run_tq1(d)
    tq2 = run_tq2(d)
    if tq1.empty or tq2.empty:
        raise RuntimeError("E7_EMPTY_RESULT")
    p1 = RESULTS / "E7_TQ1_RESULTS.csv"
    p2 = RESULTS / "E7_TQ2_RESULTS.csv"
    tq1.to_csv(p1, index=False)
    tq2.to_csv(p2, index=False)
    summary = {
        "n_transitions": int(len(d)),
        "n_organizations": int(d["LongId"].nunique()),
        "material_events_next": int(d["material_next"].sum()),
        "impact_events_next": int(d["impact_next"].sum()),
        "incident_events_next": int(d["incident_next"].sum()),
        "tq1_rows": int(len(tq1)),
        "tq2_rows": int(len(tq2)),
        "claim_boundary": (
            "lagged-wave association only; no strict temporal precedence or causality"
        ),
    }
    (RESULTS / "E7_EXECUTION_SUMMARY.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    for out in [p1, p2, RESULTS / "E7_EXECUTION_SUMMARY.json"]:
        if not out.exists() or out.stat().st_size <= 0:
            raise RuntimeError(f"MISSING_RESULT {out.name}")
    print("E7_CSLS_TEMPORAL_COMPLETED")


if __name__ == "__main__" and os.environ.get("C1_RESCUE_SOURCE_ONLY", "0") != "1":
    main()
