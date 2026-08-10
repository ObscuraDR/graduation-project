# Hướng dẫn chạy Z-Sentinel IDS trên Kali VM

## Yêu cầu trên Kali VM

```bash
sudo apt update
sudo apt install -y python3 python3-pip nodejs npm docker.io docker-compose git
sudo systemctl start docker
sudo usermod -aG docker $USER   # thêm user vào group docker
# Đăng xuất và đăng nhập lại để áp dụng group
```

---

## Bước 1 — Copy project sang Kali VM

### Cách A: Dùng git (khuyến nghị)
```bash
cd ~
git clone https://github.com/<your-repo>/graduation-project.git
cd graduation-project
```

### Cách B: Copy thủ công từ Windows
Trong PowerShell trên Windows:
```powershell
# Tìm IP của Kali VM (VirtualBox Host-Only hoặc NAT)
# Rồi dùng SCP hoặc nén zip và copy
Compress-Archive -Path "c:\github_clone\GitHub\graduation-project" -DestinationPath "c:\Users\<user>\Desktop\project.zip"
```
Sau đó copy `project.zip` sang Kali VM và giải nén.

---

## Bước 2 — Chạy setup tự động

```bash
cd ~/graduation-project
chmod +x start.sh
./start.sh
```

Script sẽ tự động:
- Kiểm tra dependencies
- Tạo `.env` và điền IP Kali vào CORS_ORIGINS
- Khởi động PostgreSQL (Docker hoặc system)
- Cài Python packages
- Tạo ML models
- Cài Node packages

---

## Bước 3 — Khởi động hệ thống

Mở **Terminal 1** — Backend:
```bash
cd ~/graduation-project
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Mở **Terminal 2** — Frontend:
```bash
cd ~/graduation-project/frontend
npm run dev -- --host 0.0.0.0
```

---

## Bước 4 — Truy cập Dashboard

| Thiết bị | URL |
|---|---|
| Từ Kali VM | `http://localhost:3000` |
| Từ Windows host | `http://<KALI_VM_IP>:3000` |
| API docs | `http://localhost:8000/docs` |

**Login:** `admin` / `admin123`

---

## Bước 5 — Kết nối máy chủ con (Agent)

Trên máy chủ con (điện thoại Kali / VM khác), copy file `backend/scripts/agent.py` rồi chạy:

```bash
# Cài dependencies trên máy chủ con
pip3 install psutil httpx

# Chạy agent (thay KALI_VM_IP bằng IP thực của Kali VM)
AGENT_SERVER_ID=1 \
AGENT_API_KEY=changeme-set-API_KEY-in-env \
IDS_API_URL=http://<KALI_VM_IP>:8000/api/servers \
AGENT_INTERVAL_SECONDS=10 \
python3 agent.py
```

> Lấy IP Kali VM: chạy `hostname -I` hoặc `ip addr show`

---

## Bước 6 — Demo tấn công

```bash
cd ~/graduation-project

# Mô phỏng DDoS
python3 backend/scripts/simulate_attack.py --type DDoS

# Mô phỏng Port Scan
python3 backend/scripts/simulate_attack.py --type PortScan

# Mô phỏng Brute Force
python3 backend/scripts/simulate_attack.py --type BruteForce
```

Xem kết quả trên Dashboard → trang **Cảnh báo** và **Phân tích AI (XAI)**

---

## Gỡ lỗi thường gặp

### Lỗi kết nối PostgreSQL
```bash
# Kiểm tra PostgreSQL đang chạy
docker compose ps postgres
# Hoặc
sudo systemctl status postgresql

# Kiểm tra kết nối
psql -h 127.0.0.1 -U ids_user -d ids_db
```

### Lỗi CORS (frontend không kết nối được backend)
```bash
# Kiểm tra IP của Kali VM
hostname -I

# Thêm IP vào .env
nano .env
# Sửa dòng CORS_ORIGINS thành:
# CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://<KALI_IP>:3000
```

### Scapy cần quyền root (packet sniffer)
```bash
# Chạy backend với sudo nếu cần dùng packet sniffer
sudo python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Hoặc cấp capability cho python3
sudo setcap cap_net_raw+eip $(which python3)
```

### Lỗi thiếu libpcap (scapy)
```bash
sudo apt install libpcap-dev -y
```

---

## Cấu trúc kết nối

```
┌─────────────────────────────────────┐
│         Kali VM (máy chủ chính)     │
│  Backend  :8000   Frontend  :3000   │
│  PostgreSQL :5432                   │
└────────────────┬────────────────────┘
                 │ HTTP (LAN hoặc Tailscale)
     ┌───────────┴───────────┐
     │                       │
┌────▼─────┐         ┌───────▼──────┐
│ Kali     │         │ Kali NetHunter│
│ Android  │         │ VirtualBox   │
│ agent.py │         │ agent.py     │
└──────────┘         └──────────────┘
```
