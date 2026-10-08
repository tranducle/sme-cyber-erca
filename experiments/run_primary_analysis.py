from pathlib import Path
import csv
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path("/Users/let/Documents/LOCAL-CODING-AGENT-MAC/DO_A_PAPER_UPGRADE")
PAPER = ROOT / "PAPERS/C1_coalignment-maturity-construct"
BASE = PAPER / "5_Experiments_Simulations/TopQ1_Experiment_Rescue_20261006"
Q0 = BASE / "00_Q0"
SCRIPTS = BASE / "02_Scripts"
RESULTS = BASE / "04_Results"
REVIEWS = BASE / "05_Reviews"

FINGERPRINT = Q0 / "Q0_FROZEN_CANDIDATE_FINGERPRINT.json"
CANDIDATE_LIST = Q0 / "Q0_REVIEW_CANDIDATE_FILES.txt"
AUTHORIZATION = REVIEWS / "Q0_FINAL_EXECUTION_AUTHORIZATION.json"
EXPECTED = Q0 / "Q0_EXPECTED_OUTPUTS.txt"
AUTH_VALUE = "REVIEWER7_ACCEPT_HARSH_PASS_Q0"


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_fingerprint():
    data = json.loads(FINGERPRINT.read_text(encoding="utf-8"))
    if "source_set_sha256" not in data or "files" not in data:
        raise RuntimeError("FINGERPRINT_SCHEMA_INVALID")
    return data


def verify_candidate():
    data = load_fingerprint()
    listed = [
        line.strip()
        for line in CANDIDATE_LIST.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    fingerprint_paths = [row["path"] for row in data["files"]]
    if listed != fingerprint_paths:
        raise RuntimeError("CANDIDATE_LIST_FINGERPRINT_PATH_MISMATCH")

    for row in data["files"]:
        path = ROOT / row["path"]
        if not path.exists():
            raise RuntimeError("CANDIDATE_FILE_MISSING " + row["path"])
        observed = sha256_file(path)
        if observed != row["sha256"]:
            raise RuntimeError("CANDIDATE_FILE_HASH_MISMATCH " + row["path"])
    return data


def verify_authorization(source_hash):
    if not AUTHORIZATION.exists():
        raise RuntimeError("FINAL_REVIEW_AUTHORIZATION_MISSING")
    data = json.loads(AUTHORIZATION.read_text(encoding="utf-8"))
    required = {
        "source_set_sha256": source_hash,
        "reviewer7": "ACCEPT",
        "harsh_reviewer": "PASS",
        "execution_authorized": True,
    }
    for key, value in required.items():
        if data.get(key) != value:
            raise RuntimeError("FINAL_REVIEW_AUTHORIZATION_INVALID " + key)
    return data


def expected_outputs():
    return [
        line.strip()
        for line in EXPECTED.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def ensure_clean_namespace():
    RESULTS.mkdir(parents=True, exist_ok=True)
    top_files = [p.name for p in RESULTS.iterdir() if p.is_file()]
    if top_files:
        raise RuntimeError(
            "STALE_CANONICAL_RESULTS " + ",".join(sorted(top_files))
        )


def quarantine_attempt(attempt_dir):
    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    target = RESULTS / ("_quarantine_" + stamp)
    target.mkdir(parents=True, exist_ok=False)
    for p in list(RESULTS.iterdir()):
        if p == target:
            continue
        if p.is_file():
            shutil.move(str(p), str(target / p.name))
    if attempt_dir.exists():
        shutil.copytree(
            attempt_dir,
            target / "execution_logs",
            dirs_exist_ok=True,
        )
    return target


def run_block(name, command, env, attempt_dir):
    stdout_path = attempt_dir / (name + "_stdout.log")
    stderr_path = attempt_dir / (name + "_stderr.log")
    with stdout_path.open("w", encoding="utf-8") as out, stderr_path.open(
        "w", encoding="utf-8"
    ) as err:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            stdout=out,
            stderr=err,
            text=True,
        )
    if proc.returncode != 0:
        raise RuntimeError(
            "EXECUTION_BLOCK_FAILED "
            + name
            + " exit="
            + str(proc.returncode)
        )


def freeze_results(source_hash, attempt_dir):
    required = expected_outputs()
    missing = []
    rows = []
    for name in required:
        path = RESULTS / name
        if not path.exists() or path.stat().st_size <= 0:
            missing.append(name)
        else:
            rows.append(
                {
                    "file": name,
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    if missing:
        raise RuntimeError("RESULT_COMPLETION_MISSING " + ",".join(missing))

    manifest = RESULTS / "RESULT_ARTIFACT_SHA256.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["file", "sha256", "bytes"]
        )
        writer.writeheader()
        writer.writerows(rows)

    completed = {
        "source_set_sha256": source_hash,
        "required_result_count": len(required),
        "execution_blocks": [
            "E1_E5_E8_8971",
            "E6_recent_CSBS",
            "E7_CSLS_temporal",
        ],
        "result_manifest_sha256": sha256_file(manifest),
        "claim_permission": (
            "none until result-integrity, result-to-claim, Reviewer7, "
            "and Harsh Reviewer gates pass"
        ),
    }
    (RESULTS / "COMPLETED.json").write_text(
        json.dumps(completed, indent=2), encoding="utf-8"
    )
    shutil.copytree(
        attempt_dir,
        RESULTS / "_execution_logs",
        dirs_exist_ok=True,
    )


def execute():
    candidate = verify_candidate()
    source_hash = candidate["source_set_sha256"]
    verify_authorization(source_hash)
    ensure_clean_namespace()

    stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    attempt_dir = REVIEWS / "execution_attempts" / stamp
    attempt_dir.mkdir(parents=True, exist_ok=False)
    (attempt_dir / "source_fingerprint.json").write_text(
        json.dumps(candidate, indent=2), encoding="utf-8"
    )

    env = os.environ.copy()
    env["C1_RESCUE_EXEC_AUTH"] = AUTH_VALUE
    env.pop("C1_RESCUE_SOURCE_ONLY", None)

    blocks = [
        (
            "E1_E5_E8_8971",
            ["Rscript", str(SCRIPTS / "run_e1_e5_e8_8971.R")],
        ),
        (
            "E6_recent_CSBS",
            ["Rscript", str(SCRIPTS / "run_e6_recent_csbs.R")],
        ),
        (
            "E7_CSLS_temporal",
            [sys.executable, str(SCRIPTS / "run_e7_csls_temporal.py")],
        ),
    ]

    try:
        for name, command in blocks:
            run_block(name, command, env, attempt_dir)
        freeze_results(source_hash, attempt_dir)
    except Exception:
        quarantine_attempt(attempt_dir)
        raise

    print("Q0_RESCUE_ALL_COMPLETED_AND_FROZEN")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "run"
    if mode == "verify":
        data = verify_candidate()
        print("Q0_CANDIDATE_VERIFY_PASS " + data["source_set_sha256"])
        return
    if mode != "run":
        raise RuntimeError("UNKNOWN_MODE " + mode)
    execute()


if __name__ == "__main__":
    main()
