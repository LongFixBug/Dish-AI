# Balance mobile

Balance là ứng dụng Flutter iOS/Android cho FoodAI. App đăng ký/đăng nhập email-mật khẩu hoặc Google, chụp/nhập món ăn, xem dinh dưỡng, ghi nhật ký bữa ăn, đặt mục tiêu và dùng chat dinh dưỡng.

## Cấu hình build

App nhận cấu hình qua `--dart-define`, không đọc `.env`. Không commit file cấu hình thật:

```bash
cd mobile
cp dart_defines.example.json dart_defines.json
```

| Khoá | Dùng cho | Ghi chú |
|---|---|---|
| `API_BASE_URL` | Mọi bản chạy | Release bắt buộc dùng HTTPS. |
| `GOOGLE_WEB_CLIENT_ID` | Google Sign-In | Web client ID mà backend dùng để xác minh ID token. |
| `IOS_CLIENT_ID` | Google Sign-In iOS | Phải khớp OAuth iOS client và URL scheme trong `ios/Runner/Info.plist`. |

`dart_defines.json` bị Git ignore vì chứa cấu hình môi trường thật. `GOOGLE_WEB_CLIENT_ID` là client ID (không phải client secret), nhưng vẫn chỉ nên phân phối qua quy trình build thay vì chép vào tài liệu public.

## Chạy local

Khởi động backend ở thư mục gốc trước:

```bash
bash scripts/dev_up.sh --no-llm
```

Sau đó chạy Flutter:

```bash
cd mobile
flutter pub get
flutter run --dart-define-from-file=dart_defines.json
```

Khi không truyền `API_BASE_URL` ở debug:

- Android emulator dùng `http://10.0.2.2:8000`.
- iOS Simulator dùng `http://127.0.0.1:8000`.

Với máy thật chạy backend trong cùng Wi-Fi, truyền IP LAN của máy phát triển:

```bash
flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
```

HTTP chỉ hợp lệ ở debug. Bản release phải trỏ tới API HTTPS production.

## Google Sign-In

Google Cloud cần có các OAuth clients trong cùng project:

- Web application client cho backend và `GOOGLE_WEB_CLIENT_ID`.
- Android client gắn đúng package name `com.longfixbug.balance` và SHA-1 của keystore release.
- iOS client gắn đúng bundle ID/URL scheme nếu phát hành iOS.

OAuth consent screen phải ở production để người ngoài danh sách test đăng nhập được. Sau thay đổi OAuth, Google có thể mất một khoảng ngắn để áp dụng.

## Build phát hành Android

```bash
cd mobile
flutter build apk --release --dart-define-from-file=dart_defines.json
flutter build appbundle --release --dart-define-from-file=dart_defines.json
```

- APK: cài trực tiếp để thử nội bộ.
- AAB: tải lên Google Play Console để phân phối qua Play Store.

Không commit `.jks`, `.keystore`, `key.properties` hay `dart_defines.json`.
