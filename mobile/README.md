# Balance mobile

Ứng dụng Flutter gọi API FoodAI để nhận diện ảnh món ăn và hiển thị dinh dưỡng.

Hồ sơ, phiên đăng nhập demo, sở thích và nhật ký được lưu cục bộ bằng
`SharedPreferences`. Auth hiện chưa có token/backend thật; luồng phân tích ảnh vẫn gọi
FastAPI thật.

## Chạy với backend local

Backend phải lắng nghe trên mọi interface để thiết bị khác truy cập được:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- Android emulator tự dùng `http://10.0.2.2:8000`.
- iOS simulator tự dùng `http://127.0.0.1:8000`.
- Máy thật cần IP LAN của máy chạy backend:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
```

Điện thoại và máy chạy backend phải ở cùng Wi-Fi. Production nên truyền URL HTTPS
qua `API_BASE_URL`; cấu hình Android chỉ cho phép HTTP cleartext ở debug build.
