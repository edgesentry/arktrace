#!/usr/bin/env bash
# Stop the Neo4j Community container for mpol-analysis.

set -euo pipefail

CONTAINER=neo4j-mpol

if docker ps --filter "name=^/${CONTAINER}$" --format '{{.Names}}' | grep -q "${CONTAINER}"; then
    echo "Stopping neo4j-mpol..."
    docker stop "${CONTAINER}"
    echo "neo4j-mpol stopped"
else
    echo "neo4j-mpol is not running"
fi
