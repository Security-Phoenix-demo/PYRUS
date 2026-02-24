#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PATTERNS_PATH = REPO_ROOT / ".github" / "sensitive-patterns.json"
DEFAULT_SKIP_FILES = {
    ".github/scripts/scan_sensitive_data.py",
    ".github/sensitive-patterns.json",
}
ACCOUNT_ID_RE = re.compile(r"\b\d{12}\b")


def load_patterns():
    with PATTERNS_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("known_account_ids", [])
    data.setdefault("anonymized_account_prefix", "")
    data.setdefault("anonymized_account_id_regexes", [])
    data.setdefault("skip_directories", [])
    data.setdefault("skip_extensions", [])
    data.setdefault("allowlist_regexes", [])
    data.setdefault("patterns", {})
    return data


def run_git(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_changed_files(base_ref=None, head_ref=None):
    if base_ref and head_ref:
        args = ["diff", "--name-only", "--diff-filter=ACMRT", f"{base_ref}...{head_ref}"]
        code, out, err = run_git(args)
        if code == 0:
            return [line for line in out.splitlines() if line.strip()]
        raise RuntimeError(f"git diff failed: {err}")

    event_name = os.getenv("GITHUB_EVENT_NAME", "")
    if event_name == "pull_request":
        base = os.getenv("GITHUB_BASE_REF")
        if base:
            base_ref = f"origin/{base}"
            return get_changed_files(base_ref=base_ref, head_ref="HEAD")

    if event_name == "push":
        before = os.getenv("GITHUB_BEFORE")
        sha = os.getenv("GITHUB_SHA")
        if before and sha and before != "0" * 40:
            return get_changed_files(base_ref=before, head_ref=sha)

    code, out, err = run_git(["diff", "--name-only", "--diff-filter=ACMRT", "HEAD~1..HEAD"])
    if code == 0:
        return [line for line in out.splitlines() if line.strip()]
    raise RuntimeError(f"git diff failed: {err}")


def is_binary_file(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(2048)
    except OSError:
        return True
    if not chunk:
        return False
    if b"\0" in chunk:
        return True
    text_chars = sum(1 for b in chunk if 32 <= b < 127 or b in b"\n\r\t\b\f")
    return (text_chars / len(chunk)) < 0.7


def is_git_ignored(path: Path) -> bool:
    code, _, _ = run_git(["check-ignore", "-q", str(path)])
    return code == 0


def should_skip_file(path: Path, config, include_ignored: bool, include_anonymized: bool) -> bool:
    rel_path = path.as_posix()
    if rel_path in DEFAULT_SKIP_FILES:
        return True
    if not include_anonymized and any(part in config["skip_directories"] for part in path.parts):
        return True
    if not include_anonymized and any("anonymized" in part for part in path.parts):
        return True
    if path.suffix in config["skip_extensions"]:
        return True
    if not include_ignored and is_git_ignored(path):
        return True
    return False


def looks_placeholder(text: str) -> bool:
    lowered = text.lower()
    placeholders = [
        "your_",
        "example",
        "changeme",
        "placeholder",
        "dummy",
        "redacted",
        "replace_me",
        "todo",
        "<redacted>",
    ]
    return any(token in lowered for token in placeholders)


def build_allowlist(allowlist_config):
    allowlist = []
    for pattern in allowlist_config:
        try:
            allowlist.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise ValueError(f"Invalid allowlist regex {pattern}: {exc}") from exc
    return allowlist


def build_account_id_allowlist(account_id_config):
    allowlist = []
    for pattern in account_id_config:
        try:
            allowlist.append(re.compile(pattern))
        except re.error as exc:
            raise ValueError(f"Invalid account id allowlist regex {pattern}: {exc}") from exc
    return allowlist


def is_anonymized_account_id(account_id: str, allowlist, anonymized_prefix: str) -> bool:
    if anonymized_prefix and account_id.startswith(anonymized_prefix):
        return True
    for pattern in allowlist:
        if pattern.fullmatch(account_id):
            return True
    return False


def is_account_id_rule(rule_name: str) -> bool:
    return rule_name == "aws_arn_with_real_account" or "account_id" in rule_name


def allowlisted(text: str, line: str, allowlist) -> bool:
    if looks_placeholder(text):
        return True
    for pattern in allowlist:
        if pattern.search(text) or pattern.search(line):
            return True
    return False


def redact_line(line: str, start: int, end: int) -> str:
    return f"{line[:start]}<REDACTED>{line[end:]}"


def scan_file(
    path: Path,
    rel_path: Path,
    patterns,
    known_ids,
    anonymized_prefix,
    account_id_allowlist,
    allowlist,
    max_findings=0,
    current_count=0,
):
    findings = []
    truncated = False
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return findings, truncated

    known_ids_re = None
    if known_ids:
        known_ids_re = re.compile("|".join(re.escape(val) for val in known_ids))

    for line_number, line in enumerate(content, start=1):
        if known_ids_re:
            match = known_ids_re.search(line)
            if match:
                findings.append((rel_path, line_number, "known_account_id", ""))

        for name, regex in patterns.items():
            for match in regex.finditer(line):
                match_text = match.group(0)
                if allowlisted(match_text, line, allowlist):
                    continue
                if is_account_id_rule(name):
                    account_ids = ACCOUNT_ID_RE.findall(match_text)
                    if account_ids and all(
                        is_anonymized_account_id(account_id, account_id_allowlist, anonymized_prefix)
                        for account_id in account_ids
                    ):
                        continue
                findings.append((rel_path, line_number, name, ""))
                if max_findings and (len(findings) + current_count) >= max_findings:
                    truncated = True
                    return findings, truncated
    return findings, truncated


def build_regexes(patterns_config):
    regexes = {}
    for name, pattern in patterns_config.items():
        try:
            regexes[name] = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"Invalid regex for {name}: {exc}") from exc
    return regexes


def normalize_paths(paths):
    normalized = []
    for path in paths:
        normalized.append(Path(path))
    return normalized


def format_findings(findings):
    lines = ["Sensitive data findings:"]
    for path, line_number, name, _ in findings:
        lines.append(f"- {path}:{line_number} [{name}]")
    return "\n".join(lines)


def format_findings_summary(findings):
    summary = {}
    for path, _, name, _ in findings:
        key = str(path)
        entry = summary.setdefault(key, {"count": 0, "rules": set()})
        entry["count"] += 1
        entry["rules"].add(name)
    lines = ["Findings by file:"]
    for path in sorted(summary):
        entry = summary[path]
        rules = ", ".join(sorted(entry["rules"]))
        lines.append(f"- {path} ({entry['count']} finding(s), rules: {rules})")
    return "\n".join(lines)


def write_report(report_path: Path, findings, scanned_files, truncated):
    report_lines = []
    if findings:
        report_lines.append("## Sensitive Data Scan")
        report_lines.append("")
        report_lines.append(format_findings(findings))
        report_lines.append("")
        report_lines.append(format_findings_summary(findings))
        report_lines.append("")
        report_lines.append(f"Total findings: {len(findings)} in {scanned_files} file(s).")
        if truncated:
            report_lines.append("Stopped early after reaching max findings limit.")
    else:
        report_lines.append("## Sensitive Data Scan")
        report_lines.append("")
        report_lines.append(f"No sensitive data findings in {scanned_files} file(s).")
    report_lines.append("")
    report_content = "\n".join(report_lines)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write(report_content)


def write_error_report(report_path: Path, error_message: str):
    report_lines = [
        "## Sensitive Data Scan",
        "",
        "Scan failed to complete.",
        "",
        f"Error: {error_message}",
        "",
        "Please review the workflow logs for details.",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines))


def main():
    parser = argparse.ArgumentParser(description="Scan changed files for sensitive data.")
    parser.add_argument("--base-ref", help="Base ref for git diff.")
    parser.add_argument("--head-ref", help="Head ref for git diff.")
    parser.add_argument(
        "--paths",
        nargs="*",
        help="Explicit file paths to scan (skips git diff).",
    )
    parser.add_argument(
        "--include-ignored",
        action="store_true",
        help="Include files matched by .gitignore rules.",
    )
    parser.add_argument(
        "--include-anonymized",
        action="store_true",
        help="Include files in anonymized directories.",
    )
    parser.add_argument(
        "--report-file",
        help="Optional path to write a redacted findings report.",
    )
    parser.add_argument(
        "--max-findings",
        type=int,
        default=0,
        help="Stop after this many findings (0 means no limit).",
    )
    args = parser.parse_args()

    try:
        config = load_patterns()
        patterns = build_regexes(config["patterns"])
        allowlist = build_allowlist(config["allowlist_regexes"])
        account_id_allowlist = build_account_id_allowlist(
            config["anonymized_account_id_regexes"]
        )
        known_ids = config["known_account_ids"]
        anonymized_prefix = config["anonymized_account_prefix"]

        if args.paths:
            paths = normalize_paths(args.paths)
        else:
            paths = [Path(path) for path in get_changed_files(args.base_ref, args.head_ref)]

        findings = []
        scanned_files = 0
        truncated_any = False
        for path in paths:
            abs_path = (REPO_ROOT / path).resolve() if not path.is_absolute() else path
            if not abs_path.exists() or abs_path.is_dir():
                continue
            rel_path = abs_path.relative_to(REPO_ROOT)
            if should_skip_file(rel_path, config, args.include_ignored, args.include_anonymized):
                continue
            if is_binary_file(abs_path):
                continue
            scanned_files += 1
            new_findings, truncated = scan_file(
                abs_path,
                rel_path,
                patterns,
                known_ids,
                anonymized_prefix,
                account_id_allowlist,
                allowlist,
                max_findings=args.max_findings,
                current_count=len(findings),
            )
            findings.extend(new_findings)
            if truncated:
                truncated_any = True
                break

        if findings:
            print("SENSITIVE DATA DETECTED")
            print(format_findings(findings))
            print()
            print(format_findings_summary(findings))
            print(f"\nTotal findings: {len(findings)} in {scanned_files} file(s).")
            if truncated_any:
                print("Stopped early after reaching max findings limit.")
            if args.report_file:
                write_report(Path(args.report_file), findings, scanned_files, truncated_any)
                print(f"Report written to: {args.report_file}")
            return 1

        if args.report_file:
            write_report(Path(args.report_file), findings, scanned_files, truncated_any)
        print(f"No sensitive data findings in {scanned_files} file(s).")
        return 0
    except Exception as exc:
        error_message = f"{exc.__class__.__name__}: {exc}"
        print("SENSITIVE DATA SCAN FAILED", file=sys.stderr)
        print(error_message, file=sys.stderr)
        if args.report_file:
            write_error_report(Path(args.report_file), error_message)
            print(f"Report written to: {args.report_file}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
