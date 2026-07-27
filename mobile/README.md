# Balance mobile

Ứng dụng Flutter gọi API FoodAI để nhận diện ảnh món ăn và hiển thị dinh dưỡng.

Hồ sơ, phiên đăng nhập demo, sở thích và nhật ký được lưu cục bộ bằng
`SharedPreferences`. Auth hiện chưa có token/backend thật; luồng phân tích ảnh vẫn gọi
FastAPI thật.

## Cấu hình lúc build (`--dart-define`)

Ứng dụng **không đọc `.env`** — mọi giá trị đều là hằng số compile-time nạp qua
`String.fromEnvironment`. Chép file mẫu rồi điền giá trị thật:

```bash
cp dart_defines.example.json dart_defines.json
flutter run --dart-define-from-file=dart_defines.json
```

`dart_defines.json` đã được gitignore vì chứa client ID thật.

| Khoá | Bắt buộc khi | Ghi chú |
|---|---|---|
| `API_BASE_URL` | Bản release | Debug tự dùng `10.0.2.2` (Android) hoặc `127.0.0.1` (iOS). Release bắt buộc HTTPS. |
| `GOOGLE_WEB_CLIENT_ID` | Muốn dùng nút "Tiếp tục với Google" | Web client ID; cũng chính là `audience` mà backend kiểm tra, nên phải trùng `GOOGLE_WEB_CLIENT_ID` trong `.env` của backend. |
| `IOS_CLIENT_ID` | Google trên iOS | Phải khớp URL scheme đã khai trong `ios/Runner/Info.plist`. |

Thiếu `GOOGLE_WEB_CLIENT_ID` thì app vẫn chạy bình thường, chỉ nút Google báo
"Thiếu GOOGLE_WEB_CLIENT_ID khi build ứng dụng" — đăng nhập bằng email/mật khẩu
không bị ảnh hưởng.

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
