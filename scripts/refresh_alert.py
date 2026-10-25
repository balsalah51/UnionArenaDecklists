#!/usr/bin/env python3
"""Open or update one GitHub issue when the refresh log needs a person.

This repository has no Slack, email, or Discord webhook. GitHub notifies
people who watch the repository (All Activity) and anyone subscribed to the
issue. The daily scrape stays green. This script exits 1 only when a warning
exists and the issue could not be filed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLE = "Data refresh warning"
STALE_HOURS = 48


def _parse_time(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def collect_warnings(
    refresh: dict,
    status: dict,
    now: datetime,
    *,
    stale_only: bool = False,
) -> list[str]:
    warnings: list[str] = []
    if not stale_only:
        unresolved = [str(cid) for cid in (status.get("unresolved") or []) if cid]
        if unresolved:
            warnings.append("Unresolved cards: " + ", ".join(unresolved))
        for row in refresh.get("failures") or []:
            if not isinstance(row, dict):
                continue
            warnings.append(
                f"Source failed: {row.get('source') or 'unknown'}: {row.get('error') or 'unknown error'}"
            )
    last = refresh.get("last_success") or {}
    newest: datetime | None = None
    if isinstance(last, dict):
        for raw in last.values():
            stamp = _parse_time(str(raw or ""))
            if stamp and (newest is None or stamp > newest):
                newest = stamp
    checked = _parse_time(str(refresh.get("checked_at") or ""))
    if checked is None:
        return warnings
    cutoff = now - timedelta(hours=STALE_HOURS)
    if newest is None or newest < cutoff:
        warnings.append(
            f"No source has succeeded in {STALE_HOURS} hours. "
            f"Last success {newest.strftime('%Y-%m-%d %H:%M UTC') if newest else 'is not recorded'}. "
            f"Last check {checked.strftime('%Y-%m-%d %H:%M UTC')}."
        )
    return warnings


def _token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _gh(args: list[str]) -> str:
    env = os.environ.copy()
    if _token():
        env["GH_TOKEN"] = _token()
    proc = subprocess.run(
        ["gh", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh failed").strip())
    return proc.stdout


def _open_issue_number() -> int | None:
    raw = _gh(
        [
            "issue",
            "list",
            "--state",
            "open",
            "--search",
            f"in:title {TITLE}",
            "--json",
            "number,title",
            "--limit",
            "10",
        ]
    )
    rows = json.loads(raw or "[]")
    for row in rows:
        if (row.get("title") or "") == TITLE:
            return int(row["number"])
    return None


def _body(warnings: list[str], now: datetime) -> str:
    lines = [
        "The daily Union Arena refresh finished and recorded a data warning.",
        "The site was still published. This issue is the alert.",
        "",
        f"Checked {now.strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
    ]
    lines.extend(f"- {line}" for line in warnings)
    lines.extend(
        [
            "",
            "Known stand-ins live in `data/card-aliases.json`. A card listed here is not one of those six.",
            "Source failures and the last successful check are in `data/refresh-log.json`.",
        ]
    )
    return "\n".join(lines) + "\n"


def publish(warnings: list[str], now: datetime) -> None:
    if not _token():
        raise RuntimeError("GH_TOKEN is not set, so the warning issue was not opened")
    body = _body(warnings, now)
    path = Path("/tmp/refresh-warning.md")
    path.write_text(body, encoding="utf-8")
    try:
        number = _open_issue_number()
        if warnings:
            if number is None:
                _gh(["issue", "create", "--title", TITLE, "--body-file", str(path)])
            else:
                _gh(["issue", "comment", str(number), "--body-file", str(path)])
            return
        if number is not None:
            _gh(
                [
                    "issue",
                    "close",
                    str(number),
                    "--comment",
                    f"Refresh is clear as of {now.strftime('%Y-%m-%d %H:%M UTC')}.",
                ]
            )
    finally:
        path.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    stale_only = "--stale-only" in args
    refresh = json.loads((ROOT / "data" / "refresh-log.json").read_text(encoding="utf-8")) if (ROOT / "data" / "refresh-log.json").is_file() else {}
    status = json.loads((ROOT / "data" / "build-status.json").read_text(encoding="utf-8")) if (ROOT / "data" / "build-status.json").is_file() else {}
    now = datetime.now(timezone.utc)
    warnings = collect_warnings(refresh, status, now, stale_only=stale_only)
    for line in warnings:
        print("REFRESH WARN", line)
    if not warnings and not _token():
        print("refresh alert: nothing to report")
        return 0
    try:
        publish(warnings, now)
    except Exception as exc:  # noqa: BLE001
        print("REFRESH ALERT FAILED", exc)
        return 1 if warnings else 0
    if warnings:
        print("refresh alert filed")
    else:
        print("refresh alert: nothing to report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
