#!/bin/bash

# -----------------------------------
# 🧪 Service Health & Routing Checker
# For payday.cd stack
# -----------------------------------

set -e  # Exit immediately if a command fails

# List of subdomains and expected status codes
declare -A SERVICES=(
    ["payday.cd"]=200
    ["wordpress.payday.cd"]=200
    ["lago.payday.cd"]=200
    ["n8n.payday.cd"]=200
    ["cmonitor.payday.cd"]=200
    ["flower.payday.cd"]=200
    ["minio.payday.cd"]=200
    ["cdn.payday.cd"]=403  # MinIO returns 403 if no bucket specified
)

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔍 Starting service health check...${NC}"

# Function to test a URL
test_service() {
    local url=$1
    local expected_code=$2
    local name=$3

    echo -n "🧪 Testing $name ($url)... "

    # Use curl to get the HTTP status code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)

    if [[ "$http_code" == "$expected_code" ]]; then
        echo -e "${GREEN}✓ Success ($http_code)${NC}"
    else
        echo -e "${RED}✗ Failed ($http_code expected $expected_code)${NC}"
    fi
}

# Function to test DNS
test_dns() {
    local domain=$1
    echo -n "🌐 Checking DNS for $domain... "
    host_result=$(dig +short "$domain" | grep -v 'IN' | head -n1)
    if [[ -n "$host_result" ]]; then
        echo -e "${GREEN}✓ Resolves to: $host_result${NC}"
    else
        echo -e "${RED}✗ Failed to resolve${NC}"
    fi
}

# Function to test HTTPS redirect
test_https_redirect() {
    local domain=$1
    echo -n "🔁 Testing HTTP → HTTPS redirect for $domain... "
    location=$(curl -s -I -L "$domain" | grep -i location | head -n1 | awk '{print $2}')
    if [[ "$location" == https* ]]; then
        echo -e "${GREEN}✓ Redirects to HTTPS${NC}"
    else
        echo -e "${YELLOW}⚠️ No redirect found${NC}"
    fi
}

# -------------------------------
# 🚀 Run Tests
# -------------------------------

echo -e "\n📌 ${YELLOW}Step 1: DNS Resolution Checks${NC}"
for domain in "${!SERVICES[@]}"; do
    test_dns "$domain"
done

echo -e "\n📌 ${YELLOW}Step 2: HTTP → HTTPS Redirect Checks${NC}"
for domain in "${!SERVICES[@]}"; do
    test_https_redirect "http://$domain"
done

echo -e "\n📌 ${YELLOW}Step 3: HTTPS Connectivity Checks${NC}"
for domain in "${!SERVICES[@]}"; do
    test_service "https://$domain" "${SERVICES[$domain]}" "$domain"
done

echo -e "\n✅ ${GREEN}Health check completed.${NC}"