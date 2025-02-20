#!/bin/bash
set -e

# Run your original script
./init.sh

# Start PostgreSQL
docker-entrypoint.sh postgres