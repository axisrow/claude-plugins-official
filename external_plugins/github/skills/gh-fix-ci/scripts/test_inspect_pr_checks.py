#!/usr/bin/env python3
"""Unit tests for inspect_pr_checks.py — pure functions only, no subprocess calls."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inspect_pr_checks import (
    extract_failure_snippet,
    extract_job_id,
    extract_run_id,
    find_failure_index,
    is_failing,
    is_log_pending_message,
    is_zip_payload,
    normalize_field,
    parse_available_fields,
    tail_lines,
)


class TestNormalizeField(unittest.TestCase):
    def test_lowercases_value(self):
        self.assertEqual(normalize_field("FAILURE"), "failure")

    def test_strips_whitespace(self):
        self.assertEqual(normalize_field("  failure  "), "failure")

    def test_none_returns_empty_string(self):
        self.assertEqual(normalize_field(None), "")

    def test_non_string_value(self):
        self.assertEqual(normalize_field(42), "42")


class TestIsFailing(unittest.TestCase):
    def test_failure_conclusion(self):
        self.assertTrue(is_failing({"conclusion": "failure"}))

    def test_cancelled_conclusion(self):
        self.assertTrue(is_failing({"conclusion": "cancelled"}))

    def test_timed_out_conclusion(self):
        self.assertTrue(is_failing({"conclusion": "timed_out"}))

    def test_action_required_conclusion(self):
        self.assertTrue(is_failing({"conclusion": "action_required"}))

    def test_failure_state(self):
        self.assertTrue(is_failing({"state": "failure"}))

    def test_error_state(self):
        self.assertTrue(is_failing({"state": "error"}))

    def test_fail_bucket(self):
        self.assertTrue(is_failing({"bucket": "fail"}))

    def test_success_is_not_failing(self):
        self.assertFalse(is_failing({"conclusion": "success", "state": "completed"}))

    def test_empty_check_is_not_failing(self):
        self.assertFalse(is_failing({}))

    def test_case_insensitive_conclusion(self):
        self.assertTrue(is_failing({"conclusion": "FAILURE"}))

    def test_status_field_used_as_fallback(self):
        self.assertTrue(is_failing({"status": "failure"}))


class TestExtractRunId(unittest.TestCase):
    def test_standard_actions_url(self):
        url = "https://github.com/owner/repo/actions/runs/12345678/jobs/99"
        self.assertEqual(extract_run_id(url), "12345678")

    def test_short_runs_url(self):
        url = "https://github.com/owner/repo/runs/12345678"
        self.assertEqual(extract_run_id(url), "12345678")

    def test_empty_url_returns_none(self):
        self.assertIsNone(extract_run_id(""))

    def test_url_without_run_id_returns_none(self):
        self.assertIsNone(extract_run_id("https://github.com/owner/repo/pulls/1"))


class TestExtractJobId(unittest.TestCase):
    def test_full_actions_url_with_job(self):
        url = "https://github.com/owner/repo/actions/runs/12345678/job/99999"
        self.assertEqual(extract_job_id(url), "99999")

    def test_short_job_url(self):
        url = "https://example.com/job/42"
        self.assertEqual(extract_job_id(url), "42")

    def test_empty_url_returns_none(self):
        self.assertIsNone(extract_job_id(""))

    def test_url_without_job_returns_none(self):
        self.assertIsNone(extract_job_id("https://github.com/owner/repo/actions/runs/123"))


class TestFindFailureIndex(unittest.TestCase):
    def test_finds_last_error_line(self):
        lines = ["ok step", "doing work", "ERROR: something broke", "cleanup"]
        self.assertEqual(find_failure_index(lines), 2)

    def test_returns_last_match_when_multiple(self):
        lines = ["error here", "more work", "fatal: crash"]
        self.assertEqual(find_failure_index(lines), 2)

    def test_returns_none_when_no_failure(self):
        lines = ["step 1 passed", "step 2 passed", "all good"]
        self.assertIsNone(find_failure_index(lines))

    def test_case_insensitive(self):
        lines = ["TRACEBACK (most recent call last)"]
        self.assertEqual(find_failure_index(lines), 0)

    def test_empty_input_returns_none(self):
        self.assertIsNone(find_failure_index([]))


class TestExtractFailureSnippet(unittest.TestCase):
    def test_returns_window_around_failure(self):
        lines = [f"line {i}" for i in range(20)]
        lines[10] = "ERROR: boom"
        snippet = extract_failure_snippet("\n".join(lines), max_lines=160, context=3)
        self.assertIn("ERROR: boom", snippet)
        self.assertIn("line 9", snippet)
        self.assertIn("line 11", snippet)

    def test_returns_tail_when_no_failure_marker(self):
        lines = [f"line {i}" for i in range(10)]
        snippet = extract_failure_snippet("\n".join(lines), max_lines=5, context=3)
        self.assertIn("line 9", snippet)
        self.assertNotIn("line 4", snippet)

    def test_empty_log_returns_empty_string(self):
        self.assertEqual(extract_failure_snippet("", max_lines=10, context=5), "")


class TestTailLines(unittest.TestCase):
    def test_returns_last_n_lines(self):
        text = "\n".join(str(i) for i in range(10))
        self.assertEqual(tail_lines(text, 3), "7\n8\n9")

    def test_zero_max_returns_empty(self):
        self.assertEqual(tail_lines("a\nb\nc", 0), "")

    def test_fewer_lines_than_max(self):
        self.assertEqual(tail_lines("a\nb", 100), "a\nb")


class TestParseAvailableFields(unittest.TestCase):
    def test_parses_fields_after_marker(self):
        message = "Error: unknown fields\nAvailable fields:\n  name\n  state\n  conclusion\n"
        fields = parse_available_fields(message)
        self.assertIn("name", fields)
        self.assertIn("state", fields)
        self.assertIn("conclusion", fields)

    def test_returns_empty_when_marker_absent(self):
        self.assertEqual(parse_available_fields("some error without fields"), [])

    def test_ignores_blank_lines(self):
        message = "Available fields:\n  name\n\n  state\n"
        fields = parse_available_fields(message)
        self.assertNotIn("", fields)


class TestIsLogPendingMessage(unittest.TestCase):
    def test_detects_still_in_progress(self):
        self.assertTrue(is_log_pending_message("Log is still in progress"))

    def test_detects_log_available_when_complete(self):
        self.assertTrue(is_log_pending_message("log will be available when it is complete"))

    def test_case_insensitive(self):
        self.assertTrue(is_log_pending_message("STILL IN PROGRESS"))

    def test_regular_error_is_not_pending(self):
        self.assertFalse(is_log_pending_message("gh: command not found"))


class TestIsZipPayload(unittest.TestCase):
    def test_zip_magic_bytes(self):
        self.assertTrue(is_zip_payload(b"PK\x03\x04rest of zip"))

    def test_text_payload_is_not_zip(self):
        self.assertFalse(is_zip_payload(b"2024-01-01T00:00:00.0000000Z some log line"))

    def test_empty_bytes_is_not_zip(self):
        self.assertFalse(is_zip_payload(b""))


if __name__ == "__main__":
    unittest.main()
