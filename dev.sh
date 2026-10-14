#!/bin/sh
cd "$(dirname "$0")"
exec .venv/bin/watchfiles ".venv/bin/python app.py" app.py smartshot
