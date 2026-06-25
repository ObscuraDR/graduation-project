import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import './Register.css';

/**
 * Register Page Component
 * Cho phép người dùng đăng ký tài khoản mới với vai trò mặc định là 'operator'.
 */
export default function Register() {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // 1. Kiểm tra khớp mật khẩu ở client
    if (formData.password !== formData.confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }

    // 2. Kiểm tra độ dài mật khẩu (theo quy định của UserCreateRequest)
    if (formData.password.length < 8) {
      setError('Mật khẩu phải có ít nhất 8 ký tự.');
      return;
    }

    setLoading(true);
    try {
      // Gọi tới endpoint backend vừa tạo
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
          password: formData.password
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        // Hiển thị lỗi từ backend (ví dụ: Tên đăng nhập đã tồn tại)
        throw new Error(data.detail || 'Đăng ký thất bại, vui lòng thử lại.');
      }

      // 3. Thông báo thành công và chuyển hướng về trang login
      alert('Đăng ký tài khoản thành công! Bạn có thể đăng nhập ngay bây giờ.');
      navigate('/login');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h2>Tạo tài khoản Z-Sentinel</h2>
        <p className="subtitle">Hệ thống giám sát và phát hiện xâm nhập</p>
        
        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="username">Tên đăng nhập</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="Nhập username (ít nhất 3 ký tự)"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="example@zsentinel.local"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Mật khẩu</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="Ít nhất 8 ký tự"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Xác nhận mật khẩu</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
            />
          </div>

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Đang đăng ký...' : 'Đăng ký ngay'}
          </button>
        </form>

        <div className="auth-footer">
          <span>Đã có tài khoản? </span>
          <Link to="/login">Đăng nhập tại đây</Link>
        </div>
      </div>
    </div>
  );
}