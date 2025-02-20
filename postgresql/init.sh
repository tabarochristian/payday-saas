#!/bin/bash
set -e

# Step 1: Install prerequisites
echo "Installing prerequisites..."
apt update
apt install -y curl gnupg lsb-release

# Step 2: Add Dalibo Labs APT repository
echo "Adding Dalibo Labs repository..."
echo "deb [arch=amd64] http://apt.dalibo.org/labs/$(lsb_release -cs) $(lsb_release -cs)-dalibo main" > /etc/apt/sources.list.d/dalibo-labs.list
curl -fsSL -o /etc/apt/trusted.gpg.d/dalibo-labs.gpg https://apt.dalibo.org/labs/debian-dalibo.gpg

# Step 3: Install PostgreSQL Anonymizer
echo "Installing PostgreSQL Anonymizer..."
apt update
apt install -y postgresql_anonymizer_17

# Step 4: Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h localhost -U $POSTGRES_USER -d $POSTGRES_DB; do
  sleep 2
done

# Step 5: Enable the anon extension in the database
echo "Enabling the anon extension..."
psql -h localhost -U $POSTGRES_USER -d $POSTGRES_DB -c "CREATE EXTENSION IF NOT EXISTS anon;"

# Step 6: Run any additional SQL scripts
echo "Running additional SQL scripts..."
psql -h localhost -U $POSTGRES_USER -d $POSTGRES_DB -f /docker-entrypoint-initdb.d/init.sql

echo "PostgreSQL Anonymizer setup completed!"