import sys
import os

# Thêm thư mục gốc vào PYTHONPATH để có thể import module backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database.connection import SessionLocal
from backend.database.repository import UserRepository
from sqlalchemy.orm import Session

def create_new_admin(username, email, password):
    """Tạo một tài khoản admin mới trực tiếp vào cơ sở dữ liệu."""
    db: Session = SessionLocal()
    try:
        # Kiểm tra xem username đã tồn tại chưa
        existing_user = UserRepository.get_by_username(db, username)
        if existing_user:
            print(f"[-] Lỗi: Tên đăng nhập '{username}' đã tồn tại.")
            return

        # Chuẩn bị dữ liệu (UserRepository.create sẽ tự động hash password)
        user_data = {
            "username": username,
            "email": email,
            "password": password,
            "role": "admin"
        }
        
        new_user = UserRepository.create(db, user_data)
        print(f"[+] Thành công: Đã tạo tài khoản admin mới!")
        print(f"    - Username: {new_user.username}")
        print(f"    - Email: {new_user.email}")
    except Exception as e:
        print(f"[-] Lỗi hệ thống: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Thay đổi thông tin bạn muốn tạo ở đây
    create_new_admin("admin_backup", "backup@zsentinel.local", "admin123456@password")