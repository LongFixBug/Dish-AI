# Food Gate label policy — Pha 0

Trạng thái: **baseline default — cần giữ nguyên trong toàn bộ intake/train/val/test
v1; các câu hỏi mở chỉ được đổi ở release sau có version mới**

Mục đích của Food Gate là quyết định ảnh có nên đi tiếp đến Vision hay không.
Nó **không** nhận diện tên món, không tính dinh dưỡng và không được dùng để sửa
tên món Vision trả về.

## Quy tắc quyết định

| Nhãn review | Ý nghĩa | Runtime ở release đầu |
| --- | --- | --- |
| `food` | Có thực phẩm hoặc đồ uống nhìn thấy đủ để người dùng muốn phân tích | Gọi Vision |
| `non_food` | Không có thực phẩm/đồ uống có thể phân tích | Chặn khi score đủ chắc chắn |
| `uncertain` | Reviewer không đủ chắc chắn ảnh có thức ăn phân tích được | Luôn gọi Vision; không dùng làm class train v1 |

`uncertain` là một **trạng thái quyết định/đánh giá**, không phải class thứ ba của
MobileNetV3 v1. Model v1 chỉ học `food` và `non_food`; vùng score ở giữa hai
threshold được backend gọi là `uncertain`.

## Ví dụ phải gán `food`

- Một hoặc nhiều món ăn đã chế biến, dù chụp cận hoặc thiếu một góc đĩa.
- Cơm, bún, phở, mì, bánh, đồ ăn vặt, trái cây, rau, thịt/cá đã chuẩn bị để ăn.
- Đồ uống có năng lượng hoặc người dùng có thể muốn phân tích: trà sữa, nước ép,
  cà phê sữa, sinh tố, bia/rượu, nước ngọt.
- Thực phẩm đóng gói khi nhìn thấy rõ chính sản phẩm và user có thể muốn tra
  dinh dưỡng; đây vẫn là `food`, dù Vision có thể sau đó chưa đọc được brand.
- Món ăn ở nền nếu vẫn đủ rõ để reviewer thấy có food trong ảnh.

## Ví dụ phải gán `non_food`

- Người, khuôn mặt, thú cưng, xe, phong cảnh, phòng/nhà cửa, quần áo, đồ gia dụng.
- Tài liệu, hóa đơn, bảng biểu, QR, logo, ứng dụng hoặc screenshot.
- Menu chữ, ảnh quảng cáo hoặc ảnh món chỉ in trên giấy/màn hình.
- Bàn trống, đĩa/tô rỗng, dao muỗng không kèm thức ăn.
- Bao bì hoàn toàn kín/không thấy thực phẩm và user không thể phân tích món từ ảnh.
- Ảnh đen, file ảnh hợp lệ nhưng không nhìn ra nội dung, hoặc vật thể ngẫu nhiên.

## Ví dụ phải gán `uncertain`

- Ảnh quá tối/rung/mờ đến mức reviewer không biết có food thật hay không.
- Thức ăn chỉ chiếm một vùng rất nhỏ, che khuất hoặc ở hậu cảnh mơ hồ.
- Hình vẽ/đồ chơi/mô hình giống món ăn nhưng không đủ bằng chứng là thực phẩm.
- Ảnh một gói/hộp mà không thể xác định có chứa thực phẩm hay không.

## Chính sách review và dữ liệu

1. Mỗi ảnh cần `label`, `review_status`, `reviewer`, `reviewed_at`, `source` và
   checksum trong manifest.
2. `uncertain` không được âm thầm ép thành `food` hoặc `non_food`; phải giữ lại
   để đo error analysis và chỉ chuyển nhãn sau review mới.
3. Ảnh user chỉ được dùng trong dataset sau khi có `consent_to_training=true`,
   `status=approved` và nhãn reviewer. Ảnh không consent không được copy vào
   dataset cục bộ.
4. Cùng một ảnh gốc, ảnh crop, ảnh đổi sáng hoặc near-duplicate phải nằm cùng
   một split.
5. Dữ liệu public phải có provenance/license; source không rõ chỉ ở review queue,
   không vào train/test release.
6. Label theo **nội dung ảnh**, không theo tên file, folder hay prediction model.

## Chính sách canonical tên món — áp dụng cho mọi family

Food Gate không dùng tên món. Sau khi Vision chạy, Catalog Normalizer tách ba
thông tin cho mọi loại món:

| Trường | Vai trò | Ví dụ |
| --- | --- | --- |
| `vision_raw_name` | Tên Vision tự do trả về, giữ để audit | `Hủ tiếu khô`, `Phở bò tái`, `Bánh mì thịt trứng` |
| `canonical_family` | Tên gom nhóm hiển thị/UI/thống kê | `Hủ tiếu`, `Phở bò`, `Bánh mì` |
| `resolved_items` | Một hoặc nhiều row PostgreSQL để tính nutrition | Đúng biến thể hủ tiếu khô; hoặc các item combo Vision tách rõ |

Không có code riêng cho `Cơm tấm`, `Phở bò`, `Bánh mì` hay family nào khác.
Family, variant và alias là dữ liệu reviewed. Một family alias chỉ đổi display
name; chỉ alias nutrition-equivalent đã review mới được phép đổi row dinh dưỡng.

## Câu hỏi cần chốt trước production block

- Có cho người dùng override một lần khi Food Gate chặn hay không?
- Family nào được ưu tiên để tạo taxonomy/review đầu tiên theo traffic thật?
- Ai có quyền approve family alias và nutrition-equivalent alias?
