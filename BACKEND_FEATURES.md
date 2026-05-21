# Các Chức Năng Của IDS Backend

Dựa vào tài liệu API và mã nguồn hiện tại của dự án, phần backend của hệ thống (IDS Backend) đang cung cấp các nhóm chức năng chính sau đây:

## 1. Quản lý cảnh báo (Alerts)
- **Lấy danh sách cảnh báo:** Lấy toàn bộ cảnh báo có hỗ trợ phân trang (`skip`, `limit`) và lọc theo mức độ nghiêm trọng (`severity`) hoặc trạng thái (`status`).
- **Xem chi tiết cảnh báo:** Truy xuất thông tin chi tiết của một cảnh báo cụ thể thông qua `alert_id`.
- **Xử lý cảnh báo (Resolve):** Cập nhật trạng thái của cảnh báo thành đã giải quyết (kèm theo ghi chú/nguyên nhân).
- **Xóa cảnh báo:** Xóa một cảnh báo khỏi hệ thống.

## 2. Dự đoán tấn công mạng (Predictions)
- **Dự đoán đơn lẻ (Single Prediction):** Gửi các đặc trưng (features) của một gói tin/luồng mạng để nhận lại kết quả dự đoán (loại tấn công, độ tin cậy, chi tiết xác suất của từng loại).
- **Dự đoán hàng loạt (Batch Prediction):** Gửi một danh sách các luồng dữ liệu mạng để hệ thống xử lý và trả về kết quả dự đoán cho toàn bộ danh sách cùng lúc.

## 3. Quản lý mô hình Machine Learning (Models)
- **Danh sách mô hình:** Lấy thông tin tất cả các mô hình học máy đang có trong hệ thống (tên, phiên bản, thuật toán, các chỉ số đánh giá như độ chính xác, recall, f1-score...).
- **Tải/Kích hoạt mô hình (Load Model):** Chọn và kích hoạt một mô hình học máy cụ thể để sử dụng cho việc dự đoán dựa trên `model_id`.

## 4. Quản lý danh sách trắng (Whitelist)
- **Xem danh sách trắng:** Lấy danh sách các địa chỉ IP/Port được cho phép (không bị chặn/cảnh báo).
- **Thêm vào danh sách trắng:** Thêm một địa chỉ IP, Port và giao thức (TCP/UDP) vào danh sách an toàn kèm theo lý do.
- **Xóa khỏi danh sách trắng:** Xóa cấu hình an toàn của một IP/Port khỏi whitelist.

## 5. Thống kê hệ thống (Statistics)
- **Thống kê Engine Cảnh báo:** Trích xuất các số liệu thống kê liên quan đến bộ máy xử lý và sinh cảnh báo.
- **Thống kê hệ thống:** Giám sát và lấy các thông số thống kê về tài nguyên, trạng thái chung của toàn hệ thống backend.

## 6. Cập nhật thời gian thực (WebSocket)
- Hỗ trợ kết nối WebSocket (`ws://localhost:8000/ws`) để truyền dữ liệu thời gian thực trực tiếp đến giao diện (frontend) với các loại tin nhắn:
  - `alert`: Bắn ngay lập tức khi có cảnh báo tấn công mới.
  - `traffic`: Cập nhật lưu lượng mạng hiện hành.
  - `status`: Thông báo thay đổi trạng thái hệ thống.

## 7. Kiểm tra trạng thái máy chủ (Health Check)
- API `GET /health` dùng để kiểm tra xem server backend có đang hoạt động bình thường không, trả về version và trạng thái hệ thống.
