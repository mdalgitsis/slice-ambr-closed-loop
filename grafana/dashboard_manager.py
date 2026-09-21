"""Create or delete the slice dashboard in Grafana.

Run as a Kubernetes Job either side of a deployment, so a dashboard arrives
with the workload and leaves with it rather than being clicked together by hand
and then drifting.

Configuration is environment-only and has no defaults for the credential: a
missing token is an error, not a fallback to something baked into the image.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

import requests

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_TOKEN = os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN", "")
DASHBOARD_FILE = os.getenv("DASHBOARD_FILE", "dashboard.json")
REQUEST_TIMEOUT = int(os.getenv("GRAFANA_TIMEOUT", "15"))

UID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,40}$")


def require_token() -> str:
    if not GRAFANA_TOKEN:
        sys.exit(
            "GRAFANA_SERVICE_ACCOUNT_TOKEN is not set. Create a Grafana service "
            "account token and pass it in as a Secret; this image ships without "
            "a default."
        )
    return GRAFANA_TOKEN


def auth_headers(content_type: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {require_token()}"}
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers


def valid_uid(uid: str) -> bool:
    return UID_PATTERN.match(uid) is not None


def load_dashboard(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        sys.exit(f"Dashboard definition {path} not found.")
    except json.JSONDecodeError as exc:
        sys.exit(f"Dashboard definition {path} is not valid JSON: {exc}")


def substitute(dashboard: dict, uid: str, title: str) -> dict:
    rendered = (
        json.dumps(dashboard)
        .replace("{dashboard_uid}", uid)
        .replace("{dashboard_title}", title)
    )
    return json.loads(rendered)


def create(uid: str, title: str) -> int:
    if not valid_uid(uid):
        sys.exit(
            f"Invalid dashboard UID {uid!r}: 1-40 characters, alphanumeric, "
            f"hyphen or underscore."
        )

    dashboard = substitute(load_dashboard(DASHBOARD_FILE), uid, title)
    payload = {"dashboard": dashboard, "overwrite": True}

    try:
        response = requests.post(
            f"{GRAFANA_URL}/api/dashboards/db",
            headers=auth_headers(content_type=True),
            data=json.dumps(payload),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        print(f"Could not reach Grafana at {GRAFANA_URL}: {exc}", file=sys.stderr)
        return 1

    if response.status_code == 200:
        created = response.json().get("uid", uid)
        print(f"Dashboard created: {GRAFANA_URL}/d/{created}")
        return 0

    print(
        f"Failed to create dashboard: {response.status_code} {response.text}",
        file=sys.stderr,
    )
    return 1


def delete(uid: str) -> int:
    if not valid_uid(uid):
        sys.exit(f"Invalid dashboard UID {uid!r}.")

    try:
        response = requests.delete(
            f"{GRAFANA_URL}/api/dashboards/uid/{uid}",
            headers=auth_headers(),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        print(f"Could not reach Grafana at {GRAFANA_URL}: {exc}", file=sys.stderr)
        return 1

    if response.status_code == 200:
        print(f"Dashboard {uid} deleted.")
        return 0

    # A dashboard that is already gone is the desired end state, so a delete
    # Job that reruns should not fail the uninstall.
    if response.status_code == 404:
        print(f"Dashboard {uid} not found; nothing to delete.")
        return 0

    print(
        f"Failed to delete dashboard: {response.status_code} {response.text}",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create or delete the slice reconfiguration dashboard."
    )
    sub = parser.add_subparsers(dest="action", required=True)

    create_parser = sub.add_parser("create", help="Create or overwrite a dashboard")
    create_parser.add_argument("dashboard_uid")
    create_parser.add_argument("dashboard_title")

    delete_parser = sub.add_parser("delete", help="Delete a dashboard")
    delete_parser.add_argument("dashboard_uid")

    args = parser.parse_args()
    if args.action == "create":
        return create(args.dashboard_uid, args.dashboard_title)
    return delete(args.dashboard_uid)


if __name__ == "__main__":
    raise SystemExit(main())
