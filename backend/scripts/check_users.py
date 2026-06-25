import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database.connection import SessionLocal
from backend.database.models import User

def list_all_users():
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("[!] Không có người dùng nào trong cơ sở dữ liệu.")
            return

        print(f"{'ID':<5} | {'Username':<15} | {'Email':<25} | {'Role':<10}")
        print("-" * 60)
        for u in users:
            print(f"{u.id:<5} | {u.username:<15} | {u.email or 'N/A':<25} | {u.role:<10}")
            
    except Exception as e:
        print(f"[-] Lỗi khi truy vấn: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    list_all_users()