import subprocess
import asyncio
import platform
import logging
import os
import httpx
from datetime import datetime, timedelta # Thêm import này
from backend.api.validation import validate_ipv4
from backend.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class FirewallManager:
    """
    Quản lý thực thi các lệnh Firewall trên Linux (iptables) và Windows (netsh).
    Yêu cầu quyền Root (Linux) hoặc Administrator (Windows).
    """
    def __init__(self, scheduler=None): # Thêm tham số scheduler
        self.os_type = platform.system()
        self._check_privileges()
        self.scheduler = scheduler # Lưu trữ scheduler

    def _check_privileges(self):
        """Kiểm tra quyền quản trị tối cao trước khi thực thi."""
        if self.os_type == "Linux":
            if os.getuid() != 0:
                logger.warning("CẢNH BÁO: Cần quyền Root để thực thi lệnh iptables.")
        elif self.os_type == "Windows":
            import ctypes
            if ctypes.windll.shell32.IsUserAnAdmin() == 0:
                logger.warning("CẢNH BÁO: Cần quyền Administrator để thực thi lệnh netsh.")

    async def block_ip(self, ip: str, reason: str = "Detected attack") -> bool:
        """Chặn một địa chỉ IP kèm theo lý do để quản trị viên dễ theo dõi."""
        try:
            ip = validate_ipv4(ip)
        except ValueError:
            logger.error(f"IP không hợp lệ, từ chối chặn: {ip}")
            return False
            
        logger.info(f"Đang tiến hành chặn IP: {ip} | Lý do: {reason}")
        
        # Chặn tại Edge (Cloudflare) nếu được bật
        if settings.enable_cloudflare_firewall:
            asyncio.create_task(self._cloudflare_block_async(ip, reason))

        # Chặn tại Host (OS Level)
        if self.os_type == "Linux":
            return await self._linux_block_async(ip, reason)
        elif self.os_type == "Windows":
            return await self._windows_block_async(ip, reason)
        return False

    async def unblock_ip(self, ip: str) -> bool:
        """Bỏ chặn một địa chỉ IP bất đồng bộ."""
        try:
            ip = validate_ipv4(ip)
        except ValueError:
            return False

        # Gỡ chặn tại Edge (Cloudflare) nếu được bật
        if settings.enable_cloudflare_firewall:
            asyncio.create_task(self._cloudflare_unblock_async(ip))

        # Gỡ chặn tại Host (OS Level)
        if self.os_type == "Linux":
            return await self._linux_unblock_async(ip)
        elif self.os_type == "Windows":
            return await self._windows_unblock_async(ip)
        return False

    # --- Linux Logic (iptables) ---

    async def _linux_block_async(self, ip: str, reason: str) -> bool:
        try:
            # Kiểm tra tồn tại bằng async
            check_proc = await asyncio.create_subprocess_exec(
                "iptables", "-C", "INPUT", "-s", ip, "-j", "DROP",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await check_proc.wait()
            if check_proc.returncode == 0:
                logger.info(f"IP {ip} đã bị chặn từ trước.")
                return True

            # Thêm rule kèm comment để quản trị viên đọc được khi dùng lệnh `iptables -L`
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-A", "INPUT", "-s", ip, "-j", "DROP",
                "-m", "comment", "--comment", f"Z-Sentinel: {reason}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Lỗi khi chặn IP trên Linux: {e}")
            return False

    async def _linux_unblock_async(self, ip: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "iptables", "-D", "INPUT", "-s", ip, "-j", "DROP",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Lỗi khi gỡ chặn IP trên Linux: {e}")
            return False

    # --- Windows Logic (netsh) ---

    async def _windows_block_async(self, ip: str, reason: str) -> bool:
        rule_name = f"Z-Sentinel-Block-{ip}"
        try:
            # Kiểm tra xem rule đã tồn tại chưa
            check_proc = await asyncio.create_subprocess_exec(
                "netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await check_proc.communicate()
            if check_proc.returncode == 0:
                logger.info(f"IP {ip} đã bị chặn từ trước trên Windows.")
                return True

            # Windows Netsh không có field comment chính thống như iptables, 
            # nhưng ta có thể đưa reason vào description (nếu dùng PowerShell) 
            # hoặc đơn giản là giữ rule_name có ý nghĩa.
            proc = await asyncio.create_subprocess_exec(
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip}",
                f"description=Z-Sentinel Auto Block: {reason}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"Lỗi khi thực thi netsh: {stderr.decode(errors='ignore')}")
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Lỗi khi chặn IP trên Windows: {e}")
            return False

    async def _windows_unblock_async(self, ip: str) -> bool:
        rule_name = f"Z-Sentinel-Block-{ip}"
        try:
            # Kiểm tra xem rule có tồn tại không trước khi xóa
            check_proc = await asyncio.create_subprocess_exec(
                "netsh", "advfirewall", "firewall", "show", "rule", f"name={rule_name}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await check_proc.communicate()
            if check_proc.returncode != 0 or f"Rule Name: {rule_name}".encode() not in stdout:
                logger.info(f"Không tìm thấy rule chặn cho IP {ip} trên Windows.")
                return False

            proc = await asyncio.create_subprocess_exec(
                "netsh", "advfirewall", "firewall", "delete", "rule", f"name={rule_name}",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            return proc.returncode == 0
        except Exception as e:
            logger.error(f"Lỗi khi gỡ chặn IP trên Windows: {e}")
            return False

    # --- Cloudflare Edge Logic ---

    async def _cloudflare_block_async(self, ip: str, reason: str) -> bool:
        """Gửi yêu cầu chặn IP lên Cloudflare WAF."""
        url = f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/firewall/access_rules/rules"
        headers = {
            "Authorization": f"Bearer {settings.cloudflare_api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "mode": "block",
            "configuration": {
                "target": "ip",
                "value": ip
            },
            "notes": f"Z-Sentinel Auto Block: {reason}"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=10.0)
                if response.status_code == 200 or response.status_code == 201:
                    logger.info(f"Cloudflare: Đã chặn IP {ip} thành công.")
                    return True
                else:
                    logger.error(f"Cloudflare: Lỗi khi chặn IP {ip}: {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Cloudflare: Lỗi kết nối API khi chặn IP: {e}")
            return False

    async def _cloudflare_unblock_async(self, ip: str) -> bool:
        """Gỡ bỏ rule chặn IP trên Cloudflare."""
        # B1: Tìm ID của rule đang chặn IP này
        search_url = f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/firewall/access_rules/rules"
        headers = {
            "Authorization": f"Bearer {settings.cloudflare_api_token}",
            "Content-Type": "application/json"
        }
        params = {"configuration.value": ip, "mode": "block"}

        try:
            async with httpx.AsyncClient() as client:
                # Tìm rule
                res = await client.get(search_url, headers=headers, params=params)
                data = res.json()
                
                if not data.get("success") or not data.get("result"):
                    logger.info(f"Cloudflare: Không tìm thấy rule nào để gỡ chặn cho IP {ip}.")
                    return False

                # B2: Xóa tất cả các rule tìm thấy cho IP này
                success = True
                for rule in data["result"]:
                    rule_id = rule["id"]
                    delete_url = f"{search_url}/{rule_id}"
                    del_res = await client.delete(delete_url, headers=headers)
                    if del_res.status_code == 200:
                        logger.info(f"Cloudflare: Đã gỡ chặn IP {ip} (Rule ID: {rule_id}).")
                    else:
                        logger.error(f"Cloudflare: Lỗi khi gỡ chặn IP {ip}: {del_res.text}")
                        success = False
                return success
        except Exception as e:
            logger.error(f"Cloudflare: Lỗi kết nối API khi gỡ chặn IP: {e}")
            return False

    async def list_cloudflare_rules_async(self) -> list:
        """Lấy danh sách các IP đang bị chặn trên Cloudflare Edge."""
        if not settings.enable_cloudflare_firewall:
            return []

        url = f"https://api.cloudflare.com/client/v4/zones/{settings.cloudflare_zone_id}/firewall/access_rules/rules"
        headers = {
            "Authorization": f"Bearer {settings.cloudflare_api_token}",
            "Content-Type": "application/json"
        }
        params = {"mode": "block", "per_page": 100}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                else:
                    logger.error(f"Cloudflare: Lỗi khi lấy danh sách rule: {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Cloudflare: Lỗi kết nối API: {e}")
            return []
            
    def schedule_unblock(self, ip: str, duration_seconds: int):
        """
        Lên lịch gỡ chặn một địa chỉ IP sau một khoảng thời gian nhất định.
        Yêu cầu một instance APScheduler được truyền vào khi khởi tạo.
        """
        if not self.scheduler:
            logger.warning(f"APScheduler chưa được khởi tạo. Không thể lên lịch gỡ chặn cho {ip}.")
            return False

        run_date = datetime.now() + timedelta(seconds=duration_seconds)
        job_id = f"unblock_{ip}_{run_date.timestamp()}" # Tạo ID duy nhất cho job

        try:
            self.scheduler.add_job(
                self.unblock_ip, 'date', run_date=run_date, args=[ip], id=job_id, replace_existing=True
            )
            logger.info(f"Đã lên lịch gỡ chặn cho IP {ip} vào lúc {run_date} (Job ID: {job_id})")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi lên lịch gỡ chặn cho IP {ip}: {e}")
            return False

if __name__ == "__main__":
    # Test nhanh module
    async def test_firewall_manager():
        fw = FirewallManager()
        test_ip = "192.168.1.250"
        
        if await fw.block_ip(test_ip, "Test reason"):
            print(f"Thành công: Đã chặn {test_ip}")
        
        # Thực hiện unblock sau khi test
        if await fw.unblock_ip(test_ip):
            print(f"Thành công: Đã gỡ chặn {test_ip}")
    asyncio.run(test_firewall_manager())