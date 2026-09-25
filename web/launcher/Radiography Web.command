#!/bin/bash
# Radiography Web - macOS launcher (double-click).
cd "$(dirname "$0")" || exit 1

PY=""
for candidate in python3 /usr/bin/python3 /usr/local/bin/python3 /opt/homebrew/bin/python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done

if [ -z "$PY" ]; then
  osascript -e 'display alert "Python 3 gerekli" message "Radiography Web icin Python 3 kurun (https://www.python.org/downloads/)." as critical' >/dev/null 2>&1
  echo "Python 3 bulunamadi. https://www.python.org/downloads/ adresinden kurun."
  read -r -p "Kapatmak icin Enter'a basin..."
  exit 1
fi

exec "$PY" serve.py "$@"
