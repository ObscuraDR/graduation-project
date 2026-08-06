#!/bin/bash
# ============================================================================
#  Z-Sentinel IDS — Kali Attack Script
#  Tấn công từ Kali vào máy chủ Windows để demo chức năng phát hiện + chặn IP
#
#  Cách dùng:
#    chmod +x kali_attack.sh
#    ./kali_attack.sh              → menu chọn loại tấn công
#    ./kali_attack.sh ddos         → SYN Flood
#    ./kali_attack.sh portscan     → Port Scan
#    ./kali_attack.sh bruteforce   → SSH Brute Force log
#    ./kali_attack.sh all          → Tất cả (trigger auto-block nhanh nhất)
#    ./kali_attack.sh cpu          → CPU spike trên chính Kali
#
#  Yêu cầu: nmap, hping3 (sudo apt install nmap hping3 -y)
# ============================================================================

# ── Cấu hình ─────────────────────────────────────────────────────────────────
TARGET="100.82.131.4"        # Tailscale IP của Windows — đổi nếu cần
TARGET_PORT=8000             # Port backend
ATTACK_TYPE="${1:-menu}"     # Loại tấn công từ tham số dòng lệnh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── Header ────────────────────────────────────────────────────────────────────
clear
echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}   Z-SENTINEL IDS — Kali Attack Script (Demo Only)         ${NC}"
echo -e "${CYAN}============================================================${NC}"
echo -e "  Target  : ${RED}${TARGET}${NC}"
echo -e "  Port    : ${TARGET_PORT}"
echo ""

# ── Kiểm tra kết nối ─────────────────────────────────────────────────────────
echo -e "${YELLOW}[>>] Kiem tra ket noi den Windows...${NC}"
if ping -c 1 -W 3 "$TARGET" &>/dev/null; then
    echo -e "${GREEN}[OK] Ket noi thanh cong den ${TARGET}${NC}"
else
    echo -e "${RED}[ERR] Khong ket noi duoc den ${TARGET}${NC}"
    echo -e "${YELLOW}      Kiem tra Tailscale co dang chay khong: tailscale status${NC}"
    exit 1
fi

# Kiểm tra backend
echo -e "${YELLOW}[>>] Kiem tra backend...${NC}"
if curl -s "http://${TARGET}:${TARGET_PORT}/health" --max-time 5 | grep -q "healthy"; then
    echo -e "${GREEN}[OK] Backend dang chay${NC}"
else
    echo -e "${RED}[ERR] Backend khong phan hoi. Hay chay start.ps1 tren Windows truoc.${NC}"
    exit 1
fi
echo ""

# ── Hàm tấn công ─────────────────────────────────────────────────────────────

attack_portscan() {
    echo -e "${RED}[ATTACK] Port Scan → ${TARGET}${NC}"
    echo -e "${YELLOW}  Dang quet 1000 ports...${NC}"

    # Kiểm tra nmap
    if ! command -v nmap &>/dev/null; then
        echo -e "${YELLOW}  Cai nmap: sudo apt install nmap -y${NC}"
        sudo apt install nmap -y -q
    fi

    nmap -sS -T4 --min-rate 500 "$TARGET" -p 1-1000 2>/dev/null
    echo -e "${GREEN}  [OK] Port scan hoan tat${NC}"
    echo -e "${YELLOW}  → Kiem tra tab Luu luong va Canh bao tren dashboard${NC}"
}

attack_synflood() {
    echo -e "${RED}[ATTACK] SYN Flood (DDoS) → ${TARGET}:80${NC}"
    echo -e "${YELLOW}  Dang flood SYN packets trong 15 giay...${NC}"

    # Kiểm tra hping3
    if ! command -v hping3 &>/dev/null; then
        echo -e "${YELLOW}  Cai hping3: sudo apt install hping3 -y${NC}"
        sudo apt install hping3 -y -q
    fi

    sudo timeout 15 hping3 -S --flood -p 80 "$TARGET" 2>/dev/null
    echo -e "${GREEN}  [OK] SYN flood hoan tat (15s)${NC}"
    echo -e "${YELLOW}  → Kiem tra alert DDoS tren dashboard${NC}"
}

attack_udpflood() {
    echo -e "${RED}[ATTACK] UDP Flood → ${TARGET}:53${NC}"
    echo -e "${YELLOW}  Dang flood UDP packets trong 10 giay...${NC}"

    sudo timeout 10 hping3 --udp --flood -p 53 "$TARGET" 2>/dev/null
    echo -e "${GREEN}  [OK] UDP flood hoan tat${NC}"
}

attack_bruteforce_log() {
    echo -e "${RED}[ATTACK] SSH Brute Force (ghi vao auth.log)${NC}"
    echo -e "${YELLOW}  Dang ghi 20 dong SSH fail vao /var/log/auth.log...${NC}"

    for i in $(seq 1 20); do
        echo "$(date '+%b %d %H:%M:%S') kali sshd[$$]: Failed password for root from $(shuf -i 10-200 -n 1).$(shuf -i 1-255 -n 1).$(shuf -i 1-255 -n 1).$(shuf -i 1-254 -n 1) port $((RANDOM % 60000 + 1024)) ssh2" | sudo tee -a /var/log/auth.log > /dev/null
        sleep 0.8
        echo -e "  Ghi dong $i/20..."
    done
    echo -e "${GREEN}  [OK] Da ghi 20 dong SSH fail${NC}"
    echo -e "${YELLOW}  → Agent se phat hien va gui alert ssh_brute_force sau ~30s${NC}"
}

attack_cpu_spike() {
    echo -e "${RED}[ATTACK] CPU Spike tren Kali${NC}"
    echo -e "${YELLOW}  Dang stress CPU trong 30 giay...${NC}"

    if ! command -v stress &>/dev/null; then
        echo -e "${YELLOW}  Cai stress: sudo apt install stress -y${NC}"
        sudo apt install stress -y -q
    fi

    stress --cpu 4 --timeout 30
    echo -e "${GREEN}  [OK] CPU spike hoan tat${NC}"
    echo -e "${YELLOW}  → Kiem tra alert cpu_spike tren trang May chu${NC}"
}

attack_all() {
    echo -e "${RED}[ATTACK] Tat ca loai tan cong — trigger AUTO-BLOCK${NC}"
    echo ""

    echo -e "${YELLOW}[1/4] Port Scan...${NC}"
    attack_portscan
    echo ""
    sleep 3

    echo -e "${YELLOW}[2/4] SYN Flood...${NC}"
    attack_synflood
    echo ""
    sleep 3

    echo -e "${YELLOW}[3/4] UDP Flood...${NC}"
    attack_udpflood
    echo ""
    sleep 3

    echo -e "${YELLOW}[4/4] Port Scan lan 2 (trigger correlation → auto-block)...${NC}"
    attack_portscan
    echo ""

    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}  Hoan tat! IP Kali se bi tu dong chan tren Firewall.${NC}"
    echo -e "${GREEN}  Kiem tra: Dashboard → Firewall → IP Dang chan${NC}"
    echo -e "${GREEN}============================================================${NC}"
}

# ── Menu ──────────────────────────────────────────────────────────────────────
show_menu() {
    echo -e "${CYAN}Chon loai tan cong:${NC}"
    echo "  [1] Port Scan             → trigger PortScan alert"
    echo "  [2] SYN Flood (DDoS)      → trigger DDoS alert"
    echo "  [3] SSH Brute Force log   → trigger ssh_brute_force alert"
    echo "  [4] CPU Spike (Kali)      → trigger cpu_spike alert"
    echo "  [5] Tat ca (auto-block)   → trigger correlation → auto-block IP"
    echo "  [0] Thoat"
    echo ""
    read -p "Nhap lua chon: " choice

    case $choice in
        1) attack_portscan ;;
        2) attack_synflood ;;
        3) attack_bruteforce_log ;;
        4) attack_cpu_spike ;;
        5) attack_all ;;
        0) exit 0 ;;
        *) echo -e "${RED}Lua chon khong hop le${NC}" ;;
    esac
}

# ── Main ──────────────────────────────────────────────────────────────────────
case "$ATTACK_TYPE" in
    ddos|syn)      attack_synflood ;;
    portscan|scan) attack_portscan ;;
    bruteforce|ssh) attack_bruteforce_log ;;
    cpu)           attack_cpu_spike ;;
    all)           attack_all ;;
    menu|*)        show_menu ;;
esac

echo ""
echo -e "${CYAN}→ Dashboard: http://localhost:3000${NC}"
echo -e "${CYAN}→ Canh bao : http://localhost:3000/alerts${NC}"
echo -e "${CYAN}→ Firewall : http://localhost:3000/firewall${NC}"
