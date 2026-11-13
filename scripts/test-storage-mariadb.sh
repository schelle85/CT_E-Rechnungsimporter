#!/usr/bin/env bash
# Only the existing isolated runner's newly created test resources; never a customer DB.
set -euo pipefail
export EXPECTED_SCHEMA=004_storage_operations
exec bash "$(dirname "$0")/test-cde-mariadb.sh"
