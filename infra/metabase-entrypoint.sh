#!/bin/sh
set -eu
export MB_DB_PASS="$(cat /run/secrets/metabase_password)"
exec /app/run_metabase.sh
