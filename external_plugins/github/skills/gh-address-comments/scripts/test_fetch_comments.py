#!/usr/bin/env python3
"""Unit tests for fetch_comments.py — tests pure logic with mocked subprocess."""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))
import fetch_comments


class TestRunJson(unittest.TestCase):
    def test_parses_valid_json(self):
        with patch("fetch_comments._run", return_value='{"key": "value"}'):
            result = fetch_comments._run_json(["gh", "something"])
        self.assertEqual(result, {"key": "value"})

    def test_raises_on_invalid_json(self):
        with patch("fetch_comments._run", return_value="not json"):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_comments._run_json(["gh", "something"])
        self.assertIn("Failed to parse JSON", str(ctx.exception))

    def test_raises_when_command_fails(self):
        with patch("fetch_comments._run", side_effect=RuntimeError("Command failed")):
            with self.assertRaises(RuntimeError):
                fetch_comments._run_json(["gh", "something"])


class TestGhApiGraphqlCommand(unittest.TestCase):
    """Verify gh api graphql is called with correct -F variables."""

    def _capture_cmd(self, *args, **kwargs):
        self._captured_cmd = args[0]
        return json.dumps(self._make_empty_payload())

    def _make_empty_payload(self):
        page = {"hasNextPage": False, "endCursor": None}
        empty = {"pageInfo": page, "nodes": []}
        pr = {
            "number": 1,
            "url": "https://github.com/o/r/pull/1",
            "title": "t",
            "state": "OPEN",
            "comments": empty,
            "reviews": empty,
            "reviewThreads": empty,
        }
        return {"data": {"repository": {"pullRequest": pr}}}

    def test_includes_owner_repo_number(self):
        with patch("fetch_comments._run", side_effect=self._capture_cmd):
            fetch_comments.gh_api_graphql("myowner", "myrepo", 42)
        cmd = self._captured_cmd
        self.assertIn("owner=myowner", cmd)
        self.assertIn("repo=myrepo", cmd)
        self.assertIn("number=42", cmd)

    def test_includes_comments_cursor_when_provided(self):
        with patch("fetch_comments._run", side_effect=self._capture_cmd):
            fetch_comments.gh_api_graphql("o", "r", 1, comments_cursor="abc123")
        self.assertIn("commentsCursor=abc123", self._captured_cmd)

    def test_no_cursor_flags_when_none(self):
        with patch("fetch_comments._run", side_effect=self._capture_cmd):
            fetch_comments.gh_api_graphql("o", "r", 1)
        cmd = self._captured_cmd
        self.assertNotIn("commentsCursor", " ".join(cmd))
        self.assertNotIn("reviewsCursor", " ".join(cmd))
        self.assertNotIn("threadsCursor", " ".join(cmd))


class TestFetchAll(unittest.TestCase):
    def _single_page_payload(self, comments=None, reviews=None, threads=None):
        page_done = {"hasNextPage": False, "endCursor": None}
        return {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 7,
                        "url": "https://github.com/o/r/pull/7",
                        "title": "My PR",
                        "state": "OPEN",
                        "comments": {"pageInfo": page_done, "nodes": comments or []},
                        "reviews": {"pageInfo": page_done, "nodes": reviews or []},
                        "reviewThreads": {"pageInfo": page_done, "nodes": threads or []},
                    }
                }
            }
        }

    def test_returns_pr_meta(self):
        payload = self._single_page_payload()
        with patch("fetch_comments.gh_api_graphql", return_value=payload):
            result = fetch_comments.fetch_all("o", "r", 7)
        self.assertEqual(result["pull_request"]["number"], 7)
        self.assertEqual(result["pull_request"]["owner"], "o")
        self.assertEqual(result["pull_request"]["repo"], "r")

    def test_collects_comments(self):
        comments = [{"id": "C1", "body": "hello", "author": {"login": "alice"}}]
        payload = self._single_page_payload(comments=comments)
        with patch("fetch_comments.gh_api_graphql", return_value=payload):
            result = fetch_comments.fetch_all("o", "r", 7)
        self.assertEqual(len(result["conversation_comments"]), 1)
        self.assertEqual(result["conversation_comments"][0]["id"], "C1")

    def test_paginates_until_no_more_pages(self):
        page1 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 7,
                        "url": "u",
                        "title": "t",
                        "state": "OPEN",
                        "comments": {
                            "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                            "nodes": [{"id": "C1"}],
                        },
                        "reviews": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
                        "reviewThreads": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
                    }
                }
            }
        }
        page2 = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "number": 7,
                        "url": "u",
                        "title": "t",
                        "state": "OPEN",
                        "comments": {
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                            "nodes": [{"id": "C2"}],
                        },
                        "reviews": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
                        "reviewThreads": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": []},
                    }
                }
            }
        }
        with patch("fetch_comments.gh_api_graphql", side_effect=[page1, page2]):
            result = fetch_comments.fetch_all("o", "r", 7)
        ids = [c["id"] for c in result["conversation_comments"]]
        self.assertEqual(ids, ["C1", "C2"])

    def test_raises_on_graphql_errors(self):
        payload = {"errors": [{"message": "Not found"}], "data": None}
        with patch("fetch_comments.gh_api_graphql", return_value=payload):
            with self.assertRaises(RuntimeError) as ctx:
                fetch_comments.fetch_all("o", "r", 7)
        self.assertIn("GraphQL errors", str(ctx.exception))

    def test_empty_result_structure(self):
        payload = self._single_page_payload()
        with patch("fetch_comments.gh_api_graphql", return_value=payload):
            result = fetch_comments.fetch_all("o", "r", 7)
        self.assertEqual(result["conversation_comments"], [])
        self.assertEqual(result["reviews"], [])
        self.assertEqual(result["review_threads"], [])


if __name__ == "__main__":
    unittest.main()
