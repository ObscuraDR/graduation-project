import sys
import os
import bcrypt

# Thêm thư mục gốc vào PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.database.connection import SessionLocal
from backend.database.models import User
from sqlalchemy.orm import Session

def reset_password(username, new_password):
    """Cập nhật mật khẩu mới cho user bất kể họ đã tồn tại hay chưa."""
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"[-] Lỗi: Không tìm thấy người dùng '{username}'.")
            return

        # Hash mật khẩu theo đúng logic của backend/api/auth.py
        pwd_bytes = new_password.encode('utf-8')[:72]
        hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

        user.password_hash = hashed
        db.commit()
        print(f"[+] Thành công: Đã cập nhật mật khẩu mới cho '{username}'!")
        print(f"    - Mật khẩu mới: {new_password}")
        
    except Exception as e:
        db.rollback()
        print(f"[-] Lỗi hệ thống: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Chạy script này để đặt lại mật khẩu cho tài khoản admin
    reset_password("admin", "admin123456@password")