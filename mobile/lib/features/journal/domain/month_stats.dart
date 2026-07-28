/// Số liệu tổng kết tháng và bố cục đống sticker.
///
/// Tách khỏi widget vì hai lý do: phép chia tuần dễ sai lệch một ngày, và bố
/// cục ngẫu nhiên PHẢI tái lập được — cùng một tháng thì sticker nằm yên một
/// chỗ, không nhảy lung tung mỗi lần màn hình dựng lại.
library;

import 'dart:math';

import 'package:balance/features/journal/domain/journal_entry.dart';

/// Bữa ăn thuộc đúng tháng đang xem.
List<JournalEntry> entriesInMonth(
  Iterable<JournalEntry> entries,
  DateTime month,
) => entries
    .where(
      (entry) =>
          entry.loggedAt.year == month.year &&
          entry.loggedAt.month == month.month,
    )
    .toList(growable: false);

/// Bữa ăn thuộc đúng năm đang xem.
List<JournalEntry> entriesInYear(Iterable<JournalEntry> entries, int year) =>
    entries
        .where((entry) => entry.loggedAt.year == year)
        .toList(growable: false);

/// Tổng món, tổng kcal và trung bình kcal mỗi món của một danh sách bữa ăn.
({int totalMeals, double totalCalories, double averageCalories}) monthTotals(
  Iterable<JournalEntry> entries,
) {
  var count = 0;
  var calories = 0.0;
  for (final entry in entries) {
    count += 1;
    calories += entry.calories;
  }
  return (
    totalMeals: count,
    totalCalories: calories,
    averageCalories: count == 0 ? 0 : calories / count,
  );
}

/// Tổng món và kcal của cả năm; dùng chung cho nhật ký và chatbot cá nhân.
({int totalMeals, double totalCalories, double averageCalories}) yearTotals(
  Iterable<JournalEntry> entries,
) => monthTotals(entries);

/// Số món theo từng "tuần" của tháng: ngày 1–7 là tuần 1, 8–14 là tuần 2...
///
/// Chia theo khối 7 ngày thay vì tuần lịch để nhãn "Tuần 1..5" luôn khớp với
/// tháng đang xem — tuần lịch có thể dính vài ngày của tháng trước.
List<int> weeklyMealCounts(DateTime month, Iterable<JournalEntry> entries) {
  final dayCount = DateTime(month.year, month.month + 1, 0).day;
  final counts = List<int>.filled((dayCount + 6) ~/ 7, 0);
  for (final entry in entriesInMonth(entries, month)) {
    counts[(entry.loggedAt.day - 1) ~/ 7] += 1;
  }
  return counts;
}

/// Một sticker đã "rơi" xong: toạ độ pixel trong khung, góc xoay và cỡ.
class DroppedSticker {
  const DroppedSticker({
    required this.left,
    required this.top,
    required this.size,
    required this.angle,
  });

  final double left;
  final double top;
  final double size;
  final double angle;
}

/// Xếp đống sticker như thể chúng rơi xuống rồi chồng lên nhau.
///
/// Mô phỏng rẻ mà nhìn đúng: chia bề ngang thành các cột hẹp, mỗi sticker rơi
/// vào một cột và đáp lên "mặt đống" hiện tại của các cột nó phủ. Không cần
/// vòng lặp vật lý — kết quả tính một lần, tái lập được theo seed, và vẫn ra
/// hình quả đồi vì cột giữa được chọn nhiều hơn.
List<DroppedSticker> dropStickers({
  required int count,
  required int seed,
  required double width,
  required double height,
  double? baseSize,
}) {
  if (count <= 0 || width <= 0 || height <= 0) return const [];
  final random = Random(seed);
  final size0 =
      baseSize ??
      fillingStickerSize(count: count, width: width, height: height);
  const columnCount = 24;
  final columnWidth = width / columnCount;
  // Mặt đống theo từng cột, tính từ ĐÁY lên (0 = chưa có gì).
  final surface = List<double>.filled(columnCount, 0);
  final placed = <DroppedSticker>[];

  for (var i = 0; i < count; i++) {
    final size = size0 * (0.82 + random.nextDouble() * 0.36);
    final span = (size / columnWidth).ceil().clamp(1, columnCount);
    // Nghiêng về giữa: trung bình hai lần bốc ngẫu nhiên cho phân bố hình
    // chuông, nên đống cao ở giữa và thoải dần ra hai bên như đổ thật.
    final centre =
        (random.nextDouble() + random.nextDouble()) / 2 * (columnCount - span);
    final start = centre.round().clamp(0, columnCount - span);

    var rest = 0.0;
    for (var c = start; c < start + span; c++) {
      if (surface[c] > rest) rest = surface[c];
    }
    // Lún vào đống một chút để các lớp chồng lấn thay vì xếp chồng ngay ngắn.
    final top = height - rest - size * 0.82;
    final newSurface = rest + size * 0.58;
    for (var c = start; c < start + span; c++) {
      surface[c] = newSurface;
    }
    placed.add(
      DroppedSticker(
        left: start * columnWidth,
        // Đống cao quá khung thì ghim lại ở mép trên: thà chồng dày còn hơn
        // sticker biến mất khỏi tầm nhìn.
        top: top < 0 ? 0 : top,
        size: size,
        angle: (random.nextDouble() - 0.5) * 0.6,
      ),
    );
  }
  return placed;
}

/// Cỡ sticker sao cho đống lấp được khung dù tháng có ít hay nhiều món.
///
/// Ba món mà vẫn dùng cỡ của ba mươi món thì khung trống hoác nửa trên; ngược
/// lại ba mươi món dùng cỡ của ba món thì tràn hết ra ngoài. Đặt tổng diện
/// tích sticker khoảng 1.7 lần diện tích khung (phần dôi ra là chỗ chồng lấn),
/// rồi kẹp trong biên để ảnh không bao giờ to quá lố hay bé như hạt đỗ.
double fillingStickerSize({
  required int count,
  required double width,
  required double height,
}) {
  if (count <= 0) return _minStickerSize;
  // Ảnh `contain` không lấp kín ô vuông của nó, nên nhân thêm hệ số phủ.
  const coverage = 0.62;
  final ideal = sqrt(1.7 * width * height / (count * coverage));
  return ideal.clamp(_minStickerSize, _maxStickerSize);
}

const double _minStickerSize = 40;
const double _maxStickerSize = 104;

/// Seed cố định theo tháng: cùng tháng thì đống sticker giữ nguyên vị trí.
int pileSeed(DateTime month) => month.year * 100 + month.month;
