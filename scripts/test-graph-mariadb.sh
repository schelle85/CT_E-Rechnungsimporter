#!/usr/bin/env bash
# Reuse the existing isolated runner, extend only its exact revision/persistence checks.
set -euo pipefail
: "${OLD_API_IMAGE:?Pass the previously accepted immutable AP01 API image ID}"
export EXPECTED_SCHEMA=003_graph_actions
exec bash "$(dirname "$0")/test-cde-mariadb.sh"
