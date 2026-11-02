#!/bin/sh
set -eu

chown -R appuser:appuser /app/output
exec gosu appuser "$@"
