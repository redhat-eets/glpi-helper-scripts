#!/usr/bin/env python3
"""
Assisted-by GLM 5.3
revoke_glpi_tokens.py — revoke GLPI user API tokens through the REST API.

Pure-API implementation (no database or container access required).
Tested against GLPI 10.0.18 (apirest.php).

What it does
    - NULLs glpi_users.api_token via  PUT /User/{id}  {"input": {"api_token": null}}
    - optionally also NULLs glpi_users.personal_token  (--personal)
    - for all users, or only those named with --user

GLPI API behaviors this relies on (verified empirically):
    - GET /User/{id} does NOT return api_token/personal_token (they are
      "undisclosed fields"), so old token values cannot be read via the API.
    - PUT /User/{id} DOES accept those fields, and a JSON null clears the
      column, fully revoking the token.
    - A session opened before revocation stays valid (session tokens are
      validated against glpi_sessions, not the user token), so it is safe
      to revoke all users, including the account whose token we used to
      authenticate. The script still revokes the caller's own account last.

Usage
    ./revoke_glpi_tokens.py --user-token <admin-api-token>              # all users
    ./revoke_glpi_tokens.py --user-token <tok> --user glpi              # one user
    ./revoke_glpi_tokens.py --user-token <tok> --user a --user b        # several
    ./revoke_glpi_tokens.py --user-token <tok> --personal         # + personal tokens
    ./revoke_glpi_tokens.py --user-token <tok> --dry-run          # preview only
    ./revoke_glpi_tokens.py --user-token <tok> --url http://glpi.example.com
                                       [--app-token <tok>]        # if a client needs it

Only the Python 3 standard library is used.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

PAGE_SIZE = 100  # users fetched per API request


class GlpiApiError(Exception):
    pass


def glpi_error(payload):
    """Return a message if the payload is a GLPI API error, else None."""
    if (
        isinstance(payload, list)
        and payload
        and isinstance(payload[0], str)
        and payload[0].startswith("ERROR_")
    ):
        return f"{payload[0]}: {payload[1] if len(payload) > 1 else ''}"
    return None


class GlpiClient:
    def __init__(self, base_url, user_token=None, app_token=None):
        self.base = base_url.rstrip("/") + "/apirest.php"
        self.user_token = user_token
        self.app_token = app_token
        self.session_token = None
        self.self_user_id = None
        self.self_user_name = None

    def _headers(self, session):
        headers = {"Content-Type": "application/json"}
        if self.app_token:
            headers["App-Token"] = self.app_token
        if session and self.session_token:
            headers["Session-Token"] = self.session_token
        elif self.user_token:
            headers["Authorization"] = f"user_token {self.user_token}"
        return headers

    def call(self, method, path, body=None, session=True):
        url = f"{self.base}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method, headers=self._headers(session)
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode() or "null")
                headers = resp.headers
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                detail = raw.strip()
                raise GlpiApiError(
                    f"HTTP {exc.code} on {method} {path}: {detail}"
                ) from None
            headers = exc.headers
        error = glpi_error(payload)
        if error:
            raise GlpiApiError(f"{method} {path}: {error}")
        return payload, headers

    def init_session(self):
        """Authenticate with the user token; also remembers who we are."""
        payload, _ = self.call(
            "GET", "initSession?get_full_session=true", session=False
        )
        self.session_token = payload["session_token"]
        session = payload.get("session", {}) or {}
        self.self_user_id = session.get("glpiID")
        self.self_user_name = session.get("glpiname")
        return self.session_token

    def get_all_users(self):
        """Fetch every user, following the Content-Range pagination."""
        users, start = [], 0
        for _ in range(1000):  # hard cap as a safety net
            payload, headers = self.call(
                "GET", f"User?range={start}-{start + PAGE_SIZE - 1}"
            )
            page = payload if isinstance(payload, list) else [payload]
            users.extend(page)
            total = None
            content_range = headers.get("Content-Range", "")
            if "/" in content_range:
                try:
                    total = int(content_range.rsplit("/", 1)[-1])
                except ValueError:
                    pass
            if total is not None:
                if len(users) >= total:
                    break
            elif len(page) < PAGE_SIZE:
                break
            if not page:
                break
            start += PAGE_SIZE
        return users

    def revoke_user_tokens(self, user_id, fields):
        """PUT a null token; returns (ok, message)."""
        payload, _ = self.call("PUT", f"User/{user_id}", body={"input": fields})
        ok, message = False, ""
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            entry = payload[0]
            message = entry.get("message", "")
            ok = any(value is True for key, value in entry.items() if key != "message")
        return ok, message

    def kill_session(self):
        try:
            self.call("GET", "killSession")
        except GlpiApiError:
            pass  # best effort logout


def parse_args():
    parser = argparse.ArgumentParser(
        description="Revoke GLPI user API tokens via the REST API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", default="http://localhost:8080",
                        help="GLPI base URL (default: http://localhost:8080)")
    parser.add_argument("--user-token", required=True,
                        help="API token of an admin account, used to authenticate")
    parser.add_argument("--app-token", default=None,
                        help="App token, if an API client requires one")
    parser.add_argument("--user", action="append", default=[], metavar="NAME",
                        help="restrict to this user (repeatable); default: all users")
    parser.add_argument("--personal", action="store_true",
                        help="also revoke personal tokens (glpi_users.personal_token)")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be done, change nothing")
    parser.add_argument("--yes", action="store_true",
                        help="do not ask for confirmation")
    return parser.parse_args()


def select_targets(users, user_names, self_user_id):
    """Filter the users to target, warn on unknown names, order caller last."""
    if user_names:
        wanted = {name.lower() for name in user_names}
        targets = [u for u in users if str(u.get("name", "")).lower() in wanted]
        found = {str(u.get("name", "")).lower() for u in targets}
        for missing in sorted(wanted - found):
            print(f"[!] warning: no such user: {missing}")
    else:
        targets = list(users)

    if not targets:
        sys.exit("error: no target users found")

    # Revoke the caller's own account last (defensive; the session stays
    # valid anyway, but this keeps failure modes simple to reason about).
    targets.sort(key=lambda u: (
        u.get("id") == self_user_id,
        str(u.get("name", "")),
    ))
    return targets


def revoke_targets(client, targets, fields):
    """Revoke tokens for each target; returns (revoked_count, failed_count)."""
    revoked, failed = 0, 0
    for user in targets:
        user_id, name = user.get("id"), user.get("name")
        try:
            ok, message = client.revoke_user_tokens(user_id, fields)
        except GlpiApiError as exc:
            ok, message = False, str(exc)
        if ok:
            revoked += 1
            print(f"    {name} (id {user_id}): revoked")
        else:
            failed += 1
            print(f"    {name} (id {user_id}): FAILED ({message})")
    return revoked, failed


def verify_revocation(url, user_token, app_token):
    """A fresh initSession must fail if the auth token was among those revoked."""
    print("[*] Verifying: fresh initSession with the authentication token...")
    checker = GlpiClient(
        url, user_token=user_token, app_token=app_token
    )
    try:
        checker.init_session()
        print("[i] token still works (its account was not in the revoked set)")
    except GlpiApiError:
        print("[ok] token is now dead - revocation confirmed")


def main():
    args = parse_args()

    fields = {"api_token": None}
    if args.personal:
        fields["personal_token"] = None

    print(f"[*] GLPI at {args.url}")
    client = GlpiClient(args.url, user_token=args.user_token, app_token=args.app_token)

    print("[*] Authenticating (initSession)...")
    try:
        client.init_session()
    except GlpiApiError as exc:
        sys.exit(f"error: authentication failed: {exc}")
    print(f"[*] Logged in as '{client.self_user_name}' (id {client.self_user_id})")

    print("[*] Fetching users...")
    try:
        users = client.get_all_users()
    except GlpiApiError as exc:
        sys.exit(f"error: could not list users: {exc}")

    targets = select_targets(users, args.user, client.self_user_id)

    preview = ", ".join(str(u.get("name")) for u in targets[:10])
    if len(targets) > 10:
        preview += ", ..."
    print(f"[*] {len(targets)} user(s) targeted: {preview}")
    print(f"[*] fields to clear: {', '.join(fields)}")

    if args.dry_run:
        print("[*] dry-run: nothing changed")
        return

    if not args.yes:
        reply = input(f"Revoke tokens for {len(targets)} user(s)? [y/N] ")
        if reply.strip().lower() not in ("y", "yes"):
            print("aborted")
            return

    revoked, failed = revoke_targets(client, targets, fields)

    client.kill_session()
    verify_revocation(args.url, args.user_token, args.app_token)

    print(f"[*] done: {revoked} revoked, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
