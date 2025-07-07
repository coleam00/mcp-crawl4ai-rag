#!/bin/bash

# Script to initialize Supabase schema using curl
# This script will be executed when the Docker container starts

echo "🚀 Initializing Supabase schema..."

# Install required dependencies
echo "📦 Installing dependencies..."
apt-get update -qq && apt-get install -y -qq curl jq

# Check if required environment variables are set
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_KEY" ]; then
    echo "❌ Error: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set"
    exit 1
fi

# Check if SQL schema file exists
if [ ! -f "/app/crawled_pages.sql" ]; then
    echo "❌ Error: Schema file not found at /app/crawled_pages.sql"
    exit 1
fi

# Check if sources table exists
echo "🔍 Checking if sources table exists..."
check_response=$(curl -s -X GET \
    "${SUPABASE_URL}/rest/v1/sources?select=source_id&limit=1" \
    -H "apikey: ${SUPABASE_SERVICE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}")

echo "API Response: $check_response"

if echo "$check_response" | grep -q -E "(error|code|42P01|does not exist)"; then
    echo "📋 Sources table doesn't exist. Creating full schema..."
    
    # Read the entire SQL schema file
    sql_content=$(cat /app/crawled_pages.sql)
    
    # Execute the full SQL schema
    echo "🔧 Executing crawled_pages.sql schema..."
    response=$(curl -s -X POST \
        "${SUPABASE_URL}/rest/v1/rpc/exec_sql" \
        -H "apikey: ${SUPABASE_SERVICE_KEY}" \
        -H "Authorization: Bearer ${SUPABASE_SERVICE_KEY}" \
        -H "Content-Type: application/json" \
        -d "{\"sql\": $(echo "$sql_content" | jq -Rs .)}")
    
    echo "Schema execution response: $response"
    
    if echo "$response" | grep -q -E "(error|code|404)"; then
        echo "❌ Error executing schema: $response"
        echo "💡 The exec_sql function is not available in Supabase."
        echo "📋 MANUAL ACTION REQUIRED:"
        echo "   1. Go to https://supabase.com/dashboard/project/uvwrdypcprzirkffjrhn"
        echo "   2. Click on 'SQL Editor' in the sidebar"
        echo "   3. Copy and paste the content of 'crawled_pages.sql'"
        echo "   4. Execute the SQL to create the required tables"
        echo "⚠️  Server will start but crawling will fail until you create the tables manually."
    else
        echo "✅ Schema initialization completed successfully!"
    fi
else
    echo "✅ Sources table already exists. Skipping schema initialization."
fi

echo "🎉 Schema initialization process finished."