#!/usr/bin/env bash
# SessionStart hook: проверяет gh auth status и предупреждает если сломан.

if ! gh auth status >/dev/null 2>&1; then
  echo '{"systemMessage": "⚠️  gh auth broken. Run: ! gh auth login -h github.com"}'
fi
exit 0
