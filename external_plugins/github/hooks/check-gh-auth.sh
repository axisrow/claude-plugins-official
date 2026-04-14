#!/usr/bin/env bash
# SessionStart hook: предупреждает только при x509/OSStatus ошибках keychain,
# чтобы сетевые сбои (оффлайн, downtime GitHub) не давали false-positive.

err=$(gh auth status 2>&1 >/dev/null) || true
if [[ "$err" == *x509* || "$err" == *OSStatus* ]]; then
  echo '{"systemMessage": "⚠️  gh auth broken. Run: ! gh auth login -h github.com"}'
fi
exit 0
