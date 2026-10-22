#!/bin/zsh
cd "${0:A:h}"
for preview_port in 8766 8765; do
  if curl --noproxy '*' -fsS --max-time 2 "http://127.0.0.1:${preview_port}/api/health" 2>/dev/null | .venv/bin/python -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("service")=="huan-terrain" else 1)' 2>/dev/null; then
    open "http://127.0.0.1:${preview_port}/"
    exit 0
  fi
done
exec .venv/bin/python server.py --port 8766 --open
