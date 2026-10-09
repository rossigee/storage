#!/bin/bash
# Copyright 2025 Ross Golder
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}MinIO Regression Test Suite${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Configuration
MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_SECURE="${MINIO_SECURE:-false}"
CONTAINER_NAME="test-minio-$(date +%s)"

# Check if MinIO is already running
if curl -s -f "http://${MINIO_ENDPOINT}/minio/health/live" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ MinIO already running at ${MINIO_ENDPOINT}${NC}"
    USE_EXISTING=1
else
    echo -e "${YELLOW}MinIO not found at ${MINIO_ENDPOINT}${NC}"
    USE_EXISTING=0

    # Try to start MinIO with Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker not found and MinIO not running${NC}"
        echo "Please either:"
        echo "  1. Start MinIO: docker run -d -p 9000:9000 minio/minio server /data"
        echo "  2. Or set MINIO_ENDPOINT to an existing MinIO server"
        exit 1
    fi

    echo -e "${YELLOW}Starting MinIO with Docker...${NC}"
    docker run --rm -d \
        -p 9000:9000 \
        -p 9001:9001 \
        -e MINIO_ROOT_USER="$MINIO_ACCESS_KEY" \
        -e MINIO_ROOT_PASSWORD="$MINIO_SECRET_KEY" \
        --name "$CONTAINER_NAME" \
        minio/minio server /data --console-address ":9001" > /dev/null 2>&1

    # Wait for MinIO to be ready
    echo -n "Waiting for MinIO to be ready"
    for i in {1..30}; do
        if curl -s -f "http://${MINIO_ENDPOINT}/minio/health/live" > /dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            break
        fi
        echo -n "."
        sleep 1
        if [ $i -eq 30 ]; then
            echo -e " ${RED}✗ (timeout)${NC}"
            docker kill "$CONTAINER_NAME" 2>/dev/null || true
            exit 1
        fi
    done

    echo -e "${GREEN}✓ MinIO started (container: $CONTAINER_NAME)${NC}"
fi

echo

# Export MinIO settings for the test script
export MINIO_ENDPOINT
export MINIO_ACCESS_KEY
export MINIO_SECRET_KEY
export MINIO_SECURE

# Run the tests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Running tests..."
echo

python3 "$SCRIPT_DIR/test_minio_regression.py"
TEST_RESULT=$?

# Cleanup if we started MinIO
if [ "$USE_EXISTING" -eq 0 ]; then
    echo
    echo -e "${YELLOW}Cleaning up MinIO container...${NC}"
    docker kill "$CONTAINER_NAME" > /dev/null 2>&1
    echo -e "${GREEN}✓ Container stopped${NC}"
fi

echo
if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}All tests passed!${NC}"
    echo -e "${GREEN}========================================${NC}"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Some tests failed${NC}"
    echo -e "${RED}========================================${NC}"
fi

exit $TEST_RESULT
