"""Offline tests for the Zetaris federated data layer (no platform required).

Everything is mocked: the suite passes with Zetaris down. The optional live test
runs only when ZETARIS_LIVE=1 is set (used to produce proofs/ artefacts).
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import Agent
from planner import parse_federated_decision
from zetaris_client import ZetarisClient, ZetarisUnavailable, _extract_rows
from zetaris_tool import ZetarisFederatedTool

CANON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "canon.json")

FAKE_RESULT = {
    "columns": ["zone", "trips"],
    "rows": [{"zone": "Midtown", "trips": "120"}, {"zone": "SoHo", "trips": "57"}],
    "row_count": 2,
    "latency_ms": 42,
    "sql": "SELECT zone, trips FROM NY_TAXI.taxi_zones LIMIT 2",
    "engine": "zetaris-lightning-rest",
}


class FakeLLM:
    def __init__(self):
        self.calls = []

    def complete(self, system, user, **kw):
        self.calls.append((system, user))
        return "Answer grounded in the provided sources."


class FakePlanner:
    def __init__(self, sql):
        self.sql = sql

    def plan(self, task, context):
        return "1. check data\n2. answer"

    def decide_federated_query(self, task, context):
        return self.sql


class FakeTool:
    def __init__(self, result=None, error=None):
        self.result = result or FAKE_RESULT
        self.error = error
        self.ran = []

    def run(self, sql, page_limit=200):
        self.ran.append(sql)
        if self.error:
            raise self.error
        return self.result

    def ground(self, question, result, recalled_memory):
        return f"GROUND::{question}::{result['row_count']}"


class TestParseFederatedDecision(unittest.TestCase):
    def test_select_line(self):
        self.assertEqual(
            parse_federated_decision("FEDERATED_SQL: SELECT 1 AS ok"),
            "SELECT 1 AS ok",
        )

    def test_with_cte_and_backticks(self):
        self.assertEqual(
            parse_federated_decision("reasoning...\nFEDERATED_SQL: `WITH t AS (SELECT 1) SELECT * FROM t`"),
            "WITH t AS (SELECT 1) SELECT * FROM t",
        )

    def test_no_federation(self):
        self.assertIsNone(parse_federated_decision("NO_FEDERATION"))
        self.assertIsNone(parse_federated_decision(""))
        self.assertIsNone(parse_federated_decision(None))

    def test_write_statements_rejected(self):
        for bad in ("DROP TABLE x", "DELETE FROM x", "SELECT 1; DROP TABLE x",
                    "INSERT INTO x VALUES (1)", "UPDATE x SET a=1", "CREATE TABLE y (a int)"):
            self.assertIsNone(parse_federated_decision("FEDERATED_SQL: " + bad), bad)

    def test_non_select_rejected(self):
        self.assertIsNone(parse_federated_decision("FEDERATED_SQL: SHOW TABLES"))


class TestExtractRows(unittest.TestCase):
    def test_columns_rows_shape(self):
        cols, rows = _extract_rows({"columns": ["a", "b"], "rows": [{"a": "1", "b": "2"}]})
        self.assertEqual(cols, ["a", "b"])
        self.assertEqual(rows, [{"a": "1", "b": "2"}])

    def test_bare_list_of_dicts(self):
        cols, rows = _extract_rows([{"x": "1"}])
        self.assertEqual(cols, ["x"])
        self.assertEqual(rows, [{"x": "1"}])

    def test_nested_data_rows(self):
        cols, rows = _extract_rows({"data": {"rows": [{"k": "v"}]}})
        self.assertEqual(rows, [{"k": "v"}])
        self.assertEqual(cols, ["k"])

    def test_value_dict_unwrapped(self):
        _, rows = _extract_rows({"rows": [{"a": {"value": "7"}}]})
        self.assertEqual(rows, [{"a": "7"}])

    def test_bad_shape_raises(self):
        with self.assertRaises(ZetarisUnavailable):
            _extract_rows({"weird": 1})


class TestRestClient(unittest.TestCase):
    def setUp(self):
        # Full env isolation: the shell running the suite must not leak
        # ZETARIS_* settings (or credentials) into the code under test.
        self._env = mock.patch.dict(os.environ, {}, clear=True)
        self._env.start()
        self.addCleanup(self._env.stop)
        os.environ["ZETARIS_PASSWORD"] = "test-only-pw"

    def _client(self):
        return ZetarisClient()

    def test_login_and_query_headers(self):
        client = self._client()
        calls = []

        def fake_post(url, payload, headers=None, timeout=120):
            calls.append((url, payload, headers))
            if url.endswith("/api/auth/login"):
                return 200, {"token": "tok123", "orgId": 7}
            return 200, {"columns": ["a"], "rows": [{"a": "1"}]}

        with mock.patch("zetaris_client._post_json", side_effect=fake_post):
            result = client.query("SELECT 1 AS a", page_limit=5)

        self.assertEqual(result["row_count"], 1)
        self.assertEqual(result["engine"], "zetaris-lightning-rest")
        login_url, login_payload, _ = calls[0]
        self.assertTrue(login_url.endswith("/api/auth/login"))
        self.assertEqual(login_payload["username"], "admin@zetaris.com")
        self.assertNotIn("test-only-pw", json.dumps(result))
        query_url, query_payload, query_headers = calls[1]
        self.assertTrue(query_url.endswith("/api/proxy/query/sql/start"))
        self.assertEqual(query_payload, {"select": "SELECT 1 AS a", "pageLimit": 5})
        self.assertEqual(query_headers["Authorization"], "Bearer tok123")
        self.assertEqual(query_headers["X-Org-ID"], "7")
        self.assertIn("X-Request-ID", query_headers)

    def test_pagination_follows_pages_then_closes(self):
        client = self._client()
        calls = []

        def fake_post(url, payload, headers=None, timeout=120):
            calls.append(url.rsplit("/", 1)[-1])
            if url.endswith("/login"):
                return 200, {"token": "t", "orgId": 1}
            if url.endswith("/start"):
                return 200, {"rows": [{"a": "1"}], "hasMore": True, "queryId": "q1"}
            if url.endswith("/page"):
                return 200, {"rows": [{"a": "2"}], "hasMore": False}
            return 200, {}

        with mock.patch("zetaris_client._post_json", side_effect=fake_post):
            result = client.query("SELECT 1 AS a")

        self.assertEqual(result["row_count"], 2)
        self.assertEqual(calls, ["login", "start", "page", "close"])

    def test_http_error_maps_to_unavailable(self):
        client = self._client()
        with mock.patch("zetaris_client._post_json", return_value=(500, "boom")):
            with self.assertRaises(ZetarisUnavailable):
                client.query("SELECT 1")

    def test_network_error_maps_to_unavailable(self):
        client = self._client()
        with mock.patch("zetaris_client._post_json", side_effect=ZetarisUnavailable("down")):
            with self.assertRaises(ZetarisUnavailable):
                client.query("SELECT 1")

    def test_jdbc_password_never_in_argv(self):
        with mock.patch.dict(os.environ, {
            "ZETARIS_TRANSPORT": "jdbc",
            "ZETARIS_JDBC_JAR": "/opt/zetaris/jdbc/ndp-jdbc-driver-test.jar",
            "ZETARIS_PASSWORD": "super-secret-pw",
        }):
            client = ZetarisClient()
            captured = {}

            def fake_run(cmd, input=None, capture_output=True, text=True, timeout=60):
                captured["cmd"] = cmd
                captured["input"] = input
                return mock.Mock(returncode=0, stdout=json.dumps({"columns": [], "rows": []}), stderr="")

            with mock.patch("zetaris_client.subprocess.run", side_effect=fake_run):
                client.query("SELECT 1 AS ok")

            argv = " ".join(captured["cmd"])
            self.assertNotIn("super-secret-pw", argv)
            self.assertIn("super-secret-pw", captured["input"])
            self.assertIn("ZetarisJdbcQuery.java", captured["cmd"][1])
            self.assertIn("--sql", captured["cmd"])

    def test_jdbc_requires_jar(self):
        with mock.patch.dict(os.environ, {"ZETARIS_TRANSPORT": "jdbc", "ZETARIS_JDBC_JAR": ""}):
            client = ZetarisClient()
            with self.assertRaises(ZetarisUnavailable):
                client.query("SELECT 1")


class TestFederatedTool(unittest.TestCase):
    def test_run_rejects_empty_sql(self):
        tool = ZetarisFederatedTool(client=mock.Mock())
        with self.assertRaises(ValueError):
            tool.run("   ")

    def test_run_delegates_to_client(self):
        client = mock.Mock()
        client.query.return_value = FAKE_RESULT
        tool = ZetarisFederatedTool(client=client)
        result = tool.run(" SELECT 1 ")
        self.assertEqual(result["row_count"], 2)
        client.query.assert_called_once_with("SELECT 1", page_limit=200)

    def test_format_rows(self):
        text = ZetarisFederatedTool.format_rows(FAKE_RESULT)
        self.assertIn("zone | trips", text)
        self.assertIn("Midtown | 120", text)

    def test_ground_joins_rows_and_memory_with_provenance(self):
        tool = ZetarisFederatedTool(client=mock.Mock())
        memory = [{"text": "Martin's favourite zone is Midtown."}]
        block = tool.ground("How many trips per zone?", FAKE_RESULT, memory)
        self.assertIn("SOURCE A — Zetaris Lightning federated SQL", block)
        self.assertIn("SOURCE B — agent memory", block)
        self.assertIn("Martin's favourite zone is Midtown.", block)
        self.assertIn("Midtown | 120", block)
        self.assertIn("Never invent rows", block)

    def test_ground_handles_empty_memory(self):
        tool = ZetarisFederatedTool(client=mock.Mock())
        block = tool.ground("q", FAKE_RESULT, [])
        self.assertIn("(no recalled memories)", block)


class TestAgentFederation(unittest.TestCase):
    def _agent(self, planner, tool, llm):
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        self.addCleanup(os.remove, path)
        return Agent(memory_path=path, canon_path=CANON, llm=llm, planner=planner, data_tool=tool)

    def test_agent_runs_federated_tool_and_reports_rows(self):
        llm = FakeLLM()
        tool = FakeTool()
        agent = self._agent(FakePlanner("SELECT zone, trips FROM NY_TAXI.taxi_zones LIMIT 2"), tool, llm)
        out = agent.run("How many trips per zone?")
        self.assertEqual(tool.ran, ["SELECT zone, trips FROM NY_TAXI.taxi_zones LIMIT 2"])
        self.assertEqual(out["federated_rows"], 2)
        self.assertIn("FEDERATED GROUNDING", llm.calls[0][0])
        self.assertTrue(out["shown"])

    def test_agent_skips_tool_when_planner_says_no(self):
        llm = FakeLLM()
        tool = FakeTool()
        agent = self._agent(FakePlanner(None), tool, llm)
        out = agent.run("What is Martin's favourite zone?")
        self.assertEqual(tool.ran, [])
        self.assertIsNone(out["federated_sql"])
        self.assertNotIn("FEDERATED GROUNDING", llm.calls[0][0])

    def test_agent_degrades_when_zetaris_down(self):
        llm = FakeLLM()
        tool = FakeTool(error=ZetarisUnavailable("down"))
        agent = self._agent(FakePlanner("SELECT 1 AS ok"), tool, llm)
        out = agent.run("How many trips per zone?")
        self.assertTrue(out["shown"])
        self.assertEqual(out["federated_rows"], 0)
        self.assertIn("federated data unavailable", llm.calls[0][0])

    def test_agent_without_tool_is_unchanged(self):
        llm = FakeLLM()
        agent = self._agent(None, None, llm)
        out = agent.run("plain question")
        self.assertTrue(out["shown"])
        self.assertIsNone(out["federated_sql"])
        self.assertNotIn("FEDERATED GROUNDING", llm.calls[0][0])


@unittest.skipUnless(os.environ.get("ZETARIS_LIVE") == "1", "set ZETARIS_LIVE=1 with the platform up")
class TestLiveZetaris(unittest.TestCase):
    def test_sample_query(self):
        tool = ZetarisFederatedTool()
        result = tool.run("SELECT 1 AS ok")
        self.assertEqual(result["row_count"], 1)


if __name__ == "__main__":
    unittest.main()
