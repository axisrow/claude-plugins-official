#!/usr/bin/env bash
# Tests for allow-gh.sh hook
# Verifies that the hook outputs valid JSON with required hookEventName field

set -euo pipefail

HOOK_SCRIPT="$(dirname "$0")/allow-gh.sh"
PASS=0
FAIL=0

run_hook() {
  local cmd="$1"
  echo "{\"tool_input\":{\"command\":\"$cmd\"}}" | bash "$HOOK_SCRIPT"
}

assert_field() {
  local test_name="$1"
  local cmd="$2"
  local field="$3"
  local expected="$4"

  output=$(run_hook "$cmd")
  actual=$(echo "$output" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['hookSpecificOutput']['$field'])" 2>/dev/null || echo "PARSE_ERROR")

  if [ "$actual" = "$expected" ]; then
    echo "PASS: $test_name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $test_name"
    echo "  command: $cmd"
    echo "  field:   hookSpecificOutput.$field"
    echo "  expected: $expected"
    echo "  actual:   $actual"
    echo "  raw output: $output"
    FAIL=$((FAIL + 1))
  fi
}

assert_no_output() {
  local test_name="$1"
  local cmd="$2"

  output=$(run_hook "$cmd")
  if [ -z "$output" ]; then
    echo "PASS: $test_name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $test_name"
    echo "  expected: (no output)"
    echo "  actual:   $output"
    FAIL=$((FAIL + 1))
  fi
}

# --- gh commands ---
assert_field "gh api — hookEventName is PreToolUse" \
  "gh api repos/owner/repo/issues" "hookEventName" "PreToolUse"

assert_field "gh api — permissionDecision is allow" \
  "gh api repos/owner/repo/issues" "permissionDecision" "allow"

assert_field "gh pr — hookEventName is PreToolUse" \
  "gh pr list" "hookEventName" "PreToolUse"

assert_field "gh pr — permissionDecision is allow" \
  "gh pr list" "permissionDecision" "allow"

# --- git commands ---
assert_field "git commit — hookEventName is PreToolUse" \
  "git commit -m 'test'" "hookEventName" "PreToolUse"

assert_field "git commit — permissionDecision is allow" \
  "git commit -m 'test'" "permissionDecision" "allow"

assert_field "git push — hookEventName is PreToolUse" \
  "git push origin main" "hookEventName" "PreToolUse"

# --- python helper scripts ---
assert_field "inspect_pr_checks.py — hookEventName is PreToolUse" \
  "python3 /path/to/skills/gh-fix-ci/scripts/inspect_pr_checks.py 123" "hookEventName" "PreToolUse"

assert_field "fetch_comments.py — hookEventName is PreToolUse" \
  "python3 /path/to/skills/gh-address-comments/scripts/fetch_comments.py 456" "hookEventName" "PreToolUse"

# --- unrelated commands should produce no output ---
assert_no_output "ls command — no output" "ls -la"
assert_no_output "npm command — no output" "npm install"

# --- JSON must be valid for all allowed commands ---
for cmd in "gh auth status" "git status" "python3 ./skills/gh-fix-ci/scripts/inspect_pr_checks.py 1"; do
  output=$(run_hook "$cmd")
  if [ -n "$output" ]; then
    if echo "$output" | python3 -m json.tool > /dev/null 2>&1; then
      echo "PASS: valid JSON for: $cmd"
      PASS=$((PASS + 1))
    else
      echo "FAIL: invalid JSON for: $cmd"
      echo "  raw output: $output"
      FAIL=$((FAIL + 1))
    fi
  fi
done

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
