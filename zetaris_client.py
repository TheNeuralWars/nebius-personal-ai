"""Zetaris Lightning client — federated SQL for the agent's data layer.

Two transports, selected with ZETARIS_TRANSPORT (default "rest"):

- "rest": the documented SQL Query API of the local Zetaris platform
  (see the platform's verify.sh: login -> /api/proxy/query/sql/start,
  with page/close for result pagination). Reaches the UI proxy on
  127.0.0.1 by default; never exposed publicly (LOCAL mode install).

- "jdbc": the Lightning JDBC driver (com.zetaris.lightning.jdbc.LightningDriver,
  jdbc:zetaris:lightning@host:port) through the tiny helper
  tools/ZetarisJdbcQuery.java (needs a local JDK). The driver jar is a
  licensed artefact: it is NOT committed here -- point ZETARIS_JDBC_JAR at
  its install path.

Configuration (all env vars, no secrets in code or logs):
  ZETARIS_UI_URL       UI/API proxy base       (default http://127.0.0.1:3300)
  ZETARIS_API_URL      REST API base           (default http://127.0.0.1:8888)
  ZETARIS_USER         login user              (default admin@zetaris.com)
  ZETARIS_PASSWORD     login password          (prefer a file via
                       ZETARIS_PASSWORD_FILE, e.g. /data/secrets/zetaris_admin_password)
  ZETARIS_TRANSPORT    "rest" | "jdbc"         (default rest)
  ZETARIS_JDBC_URL     jdbc:zetaris:lightning@localhost:10000
  ZETARIS_JDBC_JAR     path to ndp-jdbc-driver-*.jar (never committed)
  ZETARIS_JDBC_CLASS   driver class            (default the Lightning driver)
  ZETARIS_JAVA         java binary             (default java)

Credentials are read from the environment / a secrets file, sent only to the
local platform, and never printed, logged or returned in results.
"""
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import uuid

DEFAULT_UI_URL = "http://127.0.0.1:3300"
DEFAULT_API_URL = "http://127.0.0.1:8888"
DEFAULT_USER = "admin@zetaris.com"
DEFAULT_JDBC_URL = "jdbc:zetaris:lightning@localhost:10000"
DEFAULT_JDBC_CLASS = "com.zetaris.lightning.jdbc.LightningDriver"


class ZetarisUnavailable(RuntimeError):
    """The local Zetaris platform could not be reached or refused the query."""


def _config():
    return {
        "ui_url": (os.environ.get("ZETARIS_UI_URL") or DEFAULT_UI_URL).rstrip("/"),
        "api_url": (os.environ.get("ZETARIS_API_URL") or DEFAULT_API_URL).rstrip("/"),
        "user": os.environ.get("ZETARIS_USER") or DEFAULT_USER,
        "password": _password(),
        "transport": (os.environ.get("ZETARIS_TRANSPORT") or "rest").strip().lower(),
        "jdbc_url": os.environ.get("ZETARIS_JDBC_URL") or DEFAULT_JDBC_URL,
        "jdbc_jar": os.environ.get("ZETARIS_JDBC_JAR") or "",
        "jdbc_class": os.environ.get("ZETARIS_JDBC_CLASS") or DEFAULT_JDBC_CLASS,
        "java": os.environ.get("ZETARIS_JAVA") or "java",
    }


def _password():
    path = os.environ.get("ZETARIS_PASSWORD_FILE")
    if path:
        with open(path) as f:
            return f.read().strip()
    return os.environ.get("ZETARIS_PASSWORD") or ""


def _request_json(method, url, payload=None, headers=None, timeout=120):
    """HTTP JSON request, return (status, parsed_body_or_text). Raises ZetarisUnavailable on network errors."""
    data = None
    if payload is not None:
        data = json.dumps(payload).encode() if isinstance(payload, (dict, list)) else payload
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
            try:
                return r.status, json.loads(body)
            except ValueError:
                return r.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, body
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise ZetarisUnavailable(f"cannot reach Zetaris at {url}: {e.__class__.__name__}") from e


def _post_json(url, payload, headers=None, timeout=120):
    return _request_json("POST", url, payload, headers, timeout)


def _extract_rows(body):
    """Find (columns, rows) in a SQL Query API response, tolerating shape variants.

    Handles: {"columns": [...], "rows": [...]}, {"data": [...]}, {"rows": [...]},
    {"results": [...]}, {"records": [...]}, {"page": [...]}, or a bare list of
    row dicts. Row values may be scalars or dicts keyed by column name.
    """
    if isinstance(body, list):
        rows = body
    elif isinstance(body, dict):
        rows = None
        for key in ("rows", "data", "results", "records", "page", "items", "result"):
            if isinstance(body.get(key), list):
                rows = body[key]
                break
        if rows is None and isinstance(body.get("data"), dict):
            for key in ("rows", "results", "records"):
                if isinstance(body["data"].get(key), list):
                    rows = body["data"][key]
                    break
        if rows is None:
            raise ZetarisUnavailable(f"unrecognised query response shape: keys={sorted(body)[:12]}")
    else:
        raise ZetarisUnavailable(f"unrecognised query response type: {type(body).__name__}")

    columns = None
    if isinstance(body, dict):
        for key in ("columns", "schema", "fields"):
            if isinstance(body.get(key), list) and body[key]:
                columns = [
                    c if isinstance(c, str) else (c.get("name") or c.get("column") or str(c))
                    for c in body[key]
                ]
                break
    if columns is None and rows and isinstance(rows[0], dict):
        columns = list(rows[0].keys())
    if columns is None:
        columns = []
    normalised = []
    for row in rows:
        if isinstance(row, dict):
            normalised.append({k: (v.get("value") if isinstance(v, dict) and "value" in v else v)
                               for k, v in row.items()})
        else:
            normalised.append(dict(zip(columns, row if isinstance(row, list) else [row])))
    return columns, normalised


def _pagination_handle(body):
    """Return a result handle if the response says there are more pages.

    The API pages with {"records", "pageNumber", "totalPages", "queryToken"};
    an older shape uses {"hasMore", "queryId"/"handle"}.
    """
    if not isinstance(body, dict):
        return None
    if body.get("queryToken") and body.get("totalPages") is not None:
        page_no, total = body.get("pageNumber") or 1, body.get("totalPages") or 1
        if page_no < total:
            return {"queryToken": body["queryToken"], "pageNumber": page_no + 1}
        return None
    if not body.get("hasMore") and not body.get("has_more") and not body.get("more"):
        return None
    for key in ("queryId", "handle", "resultId", "id", "cursor"):
        if body.get(key):
            return {key: body[key]}
    return None


class ZetarisClient:
    """Query the local Zetaris Lightning engine over REST (or JDBC via the Java helper)."""

    def __init__(self, config=None):
        self.config = config or _config()
        self._token = None
        self._org_id = None
        self._mode = None  # "ui" (documented UI proxy) or "api" (direct REST API on 8888)

    # -- auth ------------------------------------------------------------
    def login(self):
        """Sign in: UI proxy route first (documented), then the direct REST API (8888)."""
        cfg = self.config
        if not cfg["password"]:
            raise ZetarisUnavailable("no Zetaris password configured (ZETARIS_PASSWORD[_FILE])")
        try:
            return self._login_ui()
        except ZetarisUnavailable:
            return self._login_api()

    def _login_ui(self):
        cfg = self.config
        status, body = _post_json(
            cfg["ui_url"] + "/api/auth/login",
            {"username": cfg["user"], "password": cfg["password"]},
        )
        if status != 200 or not isinstance(body, dict):
            raise ZetarisUnavailable(f"Zetaris UI login failed (HTTP {status})")
        token = body.get("token") or body.get("accessToken") or body.get("access_token")
        if not token and isinstance(body.get("tokens"), dict):
            token = body["tokens"].get("token") or body["tokens"].get("accessToken")
        if not token:
            raise ZetarisUnavailable("Zetaris UI login returned no token")
        self._token = token
        self._org_id = body.get("orgId") or body.get("org_id") or body.get("organisationId")
        self._mode = "ui"
        return {"org_id": self._org_id}

    def _login_api(self):
        """Direct API login: GET /api/v1.0/auth/login with HTTP Basic (password never in URLs)."""
        import base64
        cfg = self.config
        basic = base64.b64encode(f"{cfg['user']}:{cfg['password']}".encode()).decode()
        org = os.environ.get("ZETARIS_ORG_ID") or "1"
        status, body = _request_json(
            "GET",
            cfg["api_url"] + "/api/v1.0/auth/login",
            headers={"X-Org-ID": str(org), "Authorization": "Basic " + basic},
        )
        text = body if isinstance(body, str) else json.dumps(body)
        if status != 200:
            raise ZetarisUnavailable(f"Zetaris API login failed (HTTP {status})")
        token = None
        if isinstance(body, dict):
            token = body.get("idToken") or body.get("token") or body.get("accessToken") or body.get("access_token")
            self._org_id = body.get("orgId") or body.get("org_id") or body.get("organisationId") or org
        if not token:
            match = re.search(r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}", text)
            token = match.group(0) if match else None
        if not token:
            raise ZetarisUnavailable("Zetaris API login returned no token")
        self._token = token
        self._mode = "api"
        return {"org_id": self._org_id}

    def _headers(self):
        if not self._token:
            self.login()
        token = self._token or ""  # login() guarantees a token or raises
        headers = {
            "Authorization": "Bearer " + token,
            "X-Request-ID": str(uuid.uuid4()),
        }
        if self._org_id is not None:
            headers["X-Org-ID"] = str(self._org_id)
        return headers

    def _query_url(self, step):
        if self._mode == "api":
            return f"{self.config['api_url']}/api/v1.0/query/sql/{step}"
        return f"{self.config['ui_url']}/api/proxy/query/sql/{step}"

    # -- queries ---------------------------------------------------------
    def query(self, sql, page_limit=200, timeout=300):
        """Run federated SQL, return {"columns", "rows", "row_count", "latency_ms", "sql"}."""
        if self.config["transport"] == "jdbc":
            return self._query_jdbc(sql, timeout=timeout)
        return self._query_rest(sql, page_limit=page_limit, timeout=timeout)

    def _query_rest(self, sql, page_limit, timeout):
        cfg = self.config
        t0 = time.time()
        headers = self._headers()  # logs in first; _query_url needs the resolved mode
        try:
            status, body = _post_json(
                self._query_url("start"),
                {"select": sql, "pageLimit": int(page_limit)},
                headers=headers,
                timeout=timeout,
            )
        except ZetarisUnavailable:
            raise
        except Exception as e:  # noqa: BLE001 - transport boundary
            raise ZetarisUnavailable(f"Zetaris query failed: {e.__class__.__name__}") from e
        if status != 200:
            raise ZetarisUnavailable(f"Zetaris query failed (HTTP {status})")
        columns, rows = _extract_rows(body)

        # Follow pagination ("start / page / close") when the response says there is more.
        handle = _pagination_handle(body)
        guard = 0
        while handle is not None and guard < 50:
            guard += 1
            status, page_body = _post_json(
                self._query_url("page"),
                dict(handle),
                headers=self._headers(),
                timeout=timeout,
            )
            if status != 200:
                break
            page_cols, page_rows = _extract_rows(page_body)
            rows.extend(page_rows)
            columns = columns or page_cols
            handle = _pagination_handle(page_body)
        if guard:
            try:
                _post_json(self._query_url("close"), {}, headers=self._headers(), timeout=30)
            except ZetarisUnavailable:
                pass  # closing a finished result is best-effort

        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "latency_ms": int((time.time() - t0) * 1000),
            "sql": sql,
            "engine": "zetaris-lightning-rest",
        }

    def _query_jdbc(self, sql, timeout):
        """Run SQL through the licensed Lightning JDBC driver via tools/ZetarisJdbcQuery.java.

        The password travels on stdin, never argv. The jar path comes from
        ZETARIS_JDBC_JAR and is a licensed artefact kept out of git.
        """
        cfg = self.config
        if not cfg["jdbc_jar"]:
            raise ZetarisUnavailable("ZETARIS_JDBC_JAR is not set (licensed driver jar path)")
        helper = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "ZetarisJdbcQuery.java")
        cmd = [
            cfg["java"], helper,
            "--url", cfg["jdbc_url"],
            "--jar", cfg["jdbc_jar"],
            "--class", cfg["jdbc_class"],
            "--user", cfg["user"],
            "--sql", sql,
        ]
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                input=(cfg["password"] or "") + "\n",
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as e:
            raise ZetarisUnavailable(f"JDBC transport needs a JDK ({cfg['java']} not found)") from e
        if proc.returncode != 0:
            raise ZetarisUnavailable(f"JDBC helper failed (exit {proc.returncode})")
        try:
            body = json.loads(proc.stdout)
        except ValueError as e:
            raise ZetarisUnavailable("JDBC helper returned non-JSON output") from e
        columns, rows = _extract_rows(body)
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "latency_ms": int((time.time() - t0) * 1000),
            "sql": sql,
            "engine": "zetaris-lightning-jdbc",
        }
