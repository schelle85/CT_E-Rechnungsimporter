#!/usr/bin/env bash
# Same marked-resource runner, fresh schema005 only; no customer sources or CIFS.
set -euo pipefail
export EXPECTED_SCHEMA=005_processing
exec bash "$(dirname "$0")/test-cde-mariadb.sh"
