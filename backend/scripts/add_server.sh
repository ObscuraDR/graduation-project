#!/bin/bash
# Z-Sentinel IDS - Add Server Script
# Script tiện ích để thêm server mới vào hệ thống nhanh chóng

set -e

# Màu sắc
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Cấu hình mặc định
API_URL="${IDS_API_URL:-http://localhost:8000/api/servers}"
API_KEY="${IDS_API_KEY:-changeme-set-API_KEY-in-env}"

# Hàm hiển thị usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -n, --name NAME          Tên server (bắt buộc)"
    echo "  -i, --ip IP_ADDRESS     Địa chỉ IP (bắt buộc)"
    echo "  -o, --os OS             Hệ điều hành (mặc định: Linux)"
    echo "  -d, --desc DESCRIPTION  Mô tả server"
    echo "  -u, --url URL           API URL (mặc định: http://localhost:8000/api/servers)"
    echo "  -k, --key API_KEY       API Key"
    echo "  -h, --help              Hiển thị help"
    echo ""
    echo "Examples:"
    echo "  $0 -n kali-2 -i 100.110.195.59 -o Linux"
    echo "  $0 -n web-server -i 192.168.1.100 -o Linux -d 'Web server production'"
    echo ""
    echo "Environment Variables:"
    echo "  IDS_API_URL    URL của API servers"
    echo "  IDS_API_KEY    API Key để xác thực"
}

# Parse arguments
NAME=""
IP=""
OS="Linux"
DESC=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            NAME="$2"
            shift 2
            ;;
        -i|--ip)
            IP="$2"
            shift 2
            ;;
        -o|--os)
            OS="$2"
            shift 2
            ;;
        -d|--desc)
            DESC="$2"
            shift 2
            ;;
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        -k|--key)
            API_KEY="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Validate required fields
if [[ -z "$NAME" ]]; then
    echo -e "${RED}Error: Server name is required (-n)${NC}"
    usage
    exit 1
fi

if [[ -z "$IP" ]]; then
    echo -e "${RED}Error: IP address is required (-i)${NC}"
    usage
    exit 1
fi

# Build JSON payload
PAYLOAD=$(cat <<EOF
{
    "name": "$NAME",
    "ip_address": "$IP",
    "os": "$OS",
    "description": "$DESC"
}
EOF
)

echo -e "${YELLOW}Adding server to IDS system...${NC}"
echo "Name: $NAME"
echo "IP: $IP"
echo "OS: $OS"
echo "Description: $DESC"
echo "API URL: $API_URL"
echo ""

# Gửi request
RESPONSE=$(curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "$PAYLOAD")

# Kiểm tra response
if echo "$RESPONSE" | grep -q "id\|server_id"; then
    echo -e "${GREEN}✓ Server added successfully!${NC}"
    echo "Response: $RESPONSE"
    
    # Extract server ID
    SERVER_ID=$(echo "$RESPONSE" | grep -o '"id":[0-9]*' | grep -o '[0-9]*' || echo "$RESPONSE" | grep -o '"server_id":[0-9]*' | grep -o '[0-9]*')
    
    if [[ -n "$SERVER_ID" ]]; then
        echo ""
        echo -e "${GREEN}Server ID: $SERVER_ID${NC}"
        echo ""
        echo "To run agent on this server, use:"
        echo -e "${YELLOW}export AGENT_SERVER_ID=$SERVER_ID${NC}"
        echo -e "${YELLOW}export AGENT_API_KEY=$API_KEY${NC}"
        echo -e "${YELLOW}export IDS_API_URL=$API_URL${NC}"
        echo -e "${YELLOW}python3 agent.py${NC}"
    fi
else
    echo -e "${RED}✗ Failed to add server${NC}"
    echo "Response: $RESPONSE"
    exit 1
fi
