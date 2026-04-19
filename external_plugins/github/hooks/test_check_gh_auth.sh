#!/usr/bin/env bash
# Tests for check-gh-auth.sh
# Mocks the `gh` binary via PATH to simulate x509/OSStatus/clean auth output.

set -euo pipefail

HOOK_SCRIPT="$(dirname "$0")/check-gh-auth.sh"
PASS=0
FAIL=0

run_hook_with_gh_stderr() {
  local fake_stderr="$1"
  local fake_exitcode="${2:-1}"

  # Create a temporary fake `gh` that writes to stderr and exits
  local fake_gh
  fake_gh=$(mktemp "${TMPDIR:-/tmp}/fake-gh.XXXXXX")
  cat > "$fake_gh" <<EOF
#!/usr/bin/env bash
if [[ "\$*" == *"auth status"* ]]; then
  echo "$fake_stderr" >&2
  exit $fake_exitcode
fi
exit 0
EOF
  chmod +x "$fake_gh"

  # Prepend fake gh directory to PATH
  local fake_dir
  fake_dir=$(dirname "$fake_gh")
  ln -sf "$fake_gh" "$fake_dir/gh"

  output=$(PATH="$fake_dir:$PATH" bash "$HOOK_SCRIPT")
  local exit_code=$?

  rm -f "$fake_gh" "$fake_dir/gh"
  echo "$output"
  return $exit_code
}

assert_output_contains() {
  local test_name="$1"
  local fake_stderr="$2"
  local expected="$3"

  output=$(run_hook_with_gh_stderr "$fake_stderr" 1)
  if echo "$output" | grep -qF "$expected"; then
    echo "PASS: $test_name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $test_name"
    echo "  expected output to contain: $expected"
    echo "  actual output: $output"
    FAIL=$((FAIL + 1))
  fi
}

assert_no_output() {
  local test_name="$1"
  local fake_stderr="$2"
  local fake_exitcode="${3:-0}"

  output=$(run_hook_with_gh_stderr "$fake_stderr" "$fake_exitcode")
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

assert_valid_json() {
  local test_name="$1"
  local fake_stderr="$2"

  output=$(run_hook_with_gh_stderr "$fake_stderr" 1)
  if [ -n "$output" ] && echo "$output" | python3 -m json.tool > /dev/null 2>&1; then
    echo "PASS: $test_name"
    PASS=$((PASS + 1))
  elif [ -z "$output" ]; then
    echo "PASS: $test_name (no output — hook silent as expected)"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $test_name"
    echo "  output is not valid JSON: $output"
    FAIL=$((FAIL + 1))
  fi
}

# x509 error triggers warning
assert_output_contains \
  "x509 error triggers systemMessage" \
  "tls: failed to verify certificate: x509: certificate signed by unknown authority" \
  "gh auth broken"

# OSStatus error triggers warning
assert_output_contains \
  "OSStatus error triggers systemMessage" \
  "tls: failed to verify certificate: x509: OSStatus -26276" \
  "gh auth broken"

# Clean auth produces no output
assert_no_output \
  "clean auth produces no output" \
  "" \
  0

# Network error (not x509) produces no output — avoids false positives
assert_no_output \
  "generic network error produces no output" \
  "dial tcp: i/o timeout" \
  1

# Hook always exits 0 even on x509
exit_code=0
run_hook_with_gh_stderr "x509: something" 1 > /dev/null || exit_code=$?
if [ "$exit_code" -eq 0 ]; then
  echo "PASS: hook exits 0 even when gh fails with x509"
  PASS=$((PASS + 1))
else
  echo "FAIL: hook should exit 0, got $exit_code"
  FAIL=$((FAIL + 1))
fi

# Output is valid JSON when warning is emitted
assert_valid_json \
  "warning output is valid JSON" \
  "x509: OSStatus -26276"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
