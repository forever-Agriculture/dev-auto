#!/usr/bin/env python3
# MODULE: qa_gate.py - read-only QA acceptance check over a native BMN ask export
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


class Invalid(ValueError):
    pass


def load(path: Path) -> dict:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise Invalid(f"{path.name}: record exceeds 2 MiB")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Invalid(f"{path.name}: expected an object")
    return value


def checked_record(root: Path, bmn: str, session_run: Path | None = None) -> tuple[dict, dict]:
    brief_path, report_path = root / "qa/brief.json", root / "qa/report.json"
    brief, report = load(brief_path), load(report_path)
    run = None
    if session_run:
        run = load(session_run)
        qa = run.get("result")
        if run.get("state") != "finished" or not run.get("sessionId") or not run.get("incarnationId"):
            raise Invalid("QA session did not finish with a bound native pane")
        if not isinstance(run.get("folder"), str) or Path(run["folder"]).resolve() != root.resolve():
            raise Invalid("QA session belongs to a different record folder")
        for identity in [run.get("agent"), run.get("connection")]:
            if (not isinstance(identity, dict) or type(identity.get("pid")) is not int or identity["pid"] <= 0
                    or not isinstance(identity.get("ticks"), str) or not identity["ticks"].isascii() or not identity["ticks"].isdigit()):
                raise Invalid("QA session has no registered native agent and relay")
        digest = hashlib.sha256(json.dumps(brief, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        if brief.get("mode") != "session" or run.get("brief") != brief or run.get("inputSha256") != digest:
            raise Invalid("QA session brief differs from the native reservation")
        if not isinstance(qa, dict) or qa.get("valid") is not True or qa.get("errors") != [] or qa.get("report") != report:
            raise Invalid("native QA session report is missing, invalid or changed")
    else:
        outcome, request, manifest = load(root / "outcome.json"), load(root / "request.json"), load(root / "inputs/manifest.json")
        qa = outcome.get("qa")
        if (request.get("role") != "qa" or request.get("id") != outcome.get("id") or manifest.get("id") != request.get("id")
                or outcome.get("state") != "answered"):
            raise Invalid("QA route did not return an attributed answer")
        if not isinstance(qa, dict) or qa.get("valid") is not True or qa.get("brief") != "qa/brief.json" or qa.get("report") != "qa/report.json":
            raise Invalid("native QA report is missing or invalid")
        # BMN writes qa/ from its own input manifest and the retained native answer; a relabelled copy differs from both.
        origin = request.get("browser", {}).get("origin") if isinstance(request.get("browser"), dict) else None
        if (not isinstance(manifest.get("qa"), dict) or manifest["qa"].get("brief") != brief or not isinstance(manifest.get("browser"), dict)
                or not origin or manifest["browser"].get("origin") != origin or brief.get("target") != origin):
            raise Invalid("QA brief or target differs from the native ask's input manifest and browser request")
        answer = root / "answer.md"
        if answer.stat().st_size > 2 * 1024 * 1024 or json.loads(answer.read_text(encoding="utf-8")) != report:
            raise Invalid("QA report differs from the retained native answer")
    command = [bmn, "qa", "report", "check", str(report_path), "--brief", str(brief_path)]
    if brief.get("version") == 2:
        receipt_path = root / "host-summary.json"
        if not run or not run.get("accountsSealedAt") or receipt_path.is_symlink() or not receipt_path.resolve().is_relative_to(root.resolve()):
            raise Invalid("V2 requires a sealed native session host receipt")
        receipt = load(receipt_path)
        raw = receipt_path.read_bytes()
        reference = report.get("host_summary")
        if (not raw.endswith(b"\n") or qa.get("hostSummary") != receipt or receipt.get("qaId") != run.get("id")
                or receipt.get("briefSha256") != run.get("inputSha256") or receipt.get("revision") != brief.get("revision")
                or not isinstance(reference, dict) or set(reference) != {"receiptId", "sha256"}
                or reference.get("receiptId") != receipt.get("receiptId")
                or reference.get("sha256") != hashlib.sha256(raw[:-1]).hexdigest()):
            raise Invalid("V2 host receipt differs from the native run or report digest")
        command += ["--host-summary", str(receipt_path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        raise Invalid("BMN's shared report checker rejected this brief/report")
    if qa.get("verdict") != report.get("verdict"):
        raise Invalid("the report verdict differs from its native outcome")
    browser = load(root / "browser.json")
    if browser.get("origin") != brief.get("target"):
        raise Invalid("native browser evidence belongs to a different target")
    if run:
        connection = browser.get("connection")
        if (not isinstance(connection, dict) or browser.get("qaId") != run.get("id")
                or not run.get("id") or any(connection.get(key) != run["connection"][key] for key in ["pid", "ticks"])):
            raise Invalid("browser evidence belongs to a different native QA run or relay")
    if report["goal_check"]["execution"] == "started" and not browser.get("calls", 0) > 0:
        raise Invalid("no native browser activity supports the reported execution")
    screenshots = {shot["name"]: shot for shot in browser["screenshots"]}
    names = {name for item in report["criteria"] + report["findings"] for name in item["evidence"]}
    for name in names:
        if name == "browser.json":
            continue
        parts = Path(name).parts
        if len(parts) != 2 or parts[0] != "browser" or parts[1] not in screenshots:
            raise Invalid("report names evidence absent from the native browser record")
        shot = screenshots[parts[1]]
        path = root / name
        if not path.resolve().is_relative_to(root.resolve()):
            raise Invalid("retained screenshot leaves the QA record folder")
        contents = path.read_bytes()
        if len(contents) != shot.get("bytes") or hashlib.sha256(contents).hexdigest() != shot.get("sha256"):
            raise Invalid("retained screenshot differs from its native hash")
    return brief, report


def evaluate(args: argparse.Namespace) -> dict:
    brief, report = checked_record(args.record, args.bmn, args.session_run)
    if brief["revision"] != args.revision or brief["target"] != args.target:
        raise Invalid("QA report belongs to a different candidate or target")
    if args.prior:
        prior_brief, prior_report = checked_record(args.prior, args.bmn, args.prior_session_run)
        previous = {item["id"]: item for item in prior_report["findings"]}
        required = set(args.retest) | {key for key, item in previous.items() if item["status"] == "open"}
        supplied = {item["finding"]["id"]: item["finding"] for item in brief.get("prior_findings", [])}
        current = {item["id"]: item for item in report["findings"]}
        closing = {key for key in required if current.get(key, {}).get("status") == "resolved"}
        if (set(args.retest) | closing) and brief["revision"] == prior_brief["revision"]:
            raise Invalid("an unchanged candidate is not a verified fix recheck")
        for key in required:
            if key not in previous or supplied.get(key) != previous[key]:
                raise Invalid(f"{key}: prior finding facts are missing or changed")
            retest = current.get(key, {}).get("retest", {})
            if not retest.get("steps") or not str(retest.get("observations", "")).strip():
                raise Invalid(f"{key}: no current original-repro retest; open status alone proves nothing")
    elif args.prior_session_run:
        raise Invalid("--prior-session-run requires --prior")
    elif args.retest:
        raise Invalid("--retest requires the earlier admitted --prior record")
    return {"status": "blocked" if report["verdict"] == "NO-GO" else "pass", "verdict": report["verdict"],
            "goal": report["goal_check"]["status"], "revision": brief["revision"], "target": brief["target"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--bmn", default="bmn", help="BMN CLI executable; report validation opens no socket")
    parser.add_argument("--session-run", type=Path, help="native bmn qa wait JSON receipt for this record folder")
    parser.add_argument("--prior-session-run", type=Path, help="native wait receipt when --prior is a session record")
    parser.add_argument("--prior", type=Path)
    parser.add_argument("--retest", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = evaluate(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        result = {"status": "invalid", "verdict": None, "reason": str(error)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
