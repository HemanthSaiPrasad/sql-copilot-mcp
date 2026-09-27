#!/usr/bin/env bash
# Downloads the Pagila sample database (public, free) into db/init/
set -euo pipefail

BASE="https://raw.githubusercontent.com/devrimgunduz/pagila/master"
curl -fsSL "$BASE/pagila-schema.sql" -o db/init/01-schema.sql
curl -fsSL "$BASE/pagila-data.sql"   -o db/init/02-data.sql
echo "Pagila downloaded into db/init/"
