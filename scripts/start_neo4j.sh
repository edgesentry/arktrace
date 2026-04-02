#!/usr/bin/env bash
# Start the Neo4j Community container for arktrace.
# Idempotent: restarts if stopped, creates if absent.

set -euo pipefail

CONTAINER=neo4j-mpol

if docker ps --filter "name=^/${CONTAINER}$" --format '{{.Names}}' | grep -q "${CONTAINER}"; then
    echo "neo4j-mpol is already running"
    exit 0
fi

if docker ps -a --filter "name=^/${CONTAINER}$" --format '{{.Names}}' | grep -q "${CONTAINER}"; then
    echo "Restarting existing neo4j-mpol container..."
    docker start "${CONTAINER}"
else
    echo "Creating and starting neo4j-mpol container..."
    docker run -d \
        --name "${CONTAINER}" \
        -p 7474:7474 -p 7687:7687 \
        -e NEO4J_AUTH=neo4j/password \
        -e NEO4J_PLUGINS='["graph-data-science"]' \
        neo4j:2026.03.1-community
fi

echo "Waiting for Neo4j to be ready..."
until docker exec "${CONTAINER}" cypher-shell -u neo4j -p password "RETURN 1" > /dev/null 2>&1; do
    sleep 2
done
echo "Neo4j is ready at bolt://localhost:7687"
