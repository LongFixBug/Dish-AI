/// Dựng lưới ngày cho lịch tháng và gom bữa ăn theo từng ngày.
///
/// Tách khỏi widget vì đây là phần dễ sai nhất: lệch một ô là cả tháng lệch
/// thứ, và lỗi kiểu đó rất khó thấy bằng mắt trên màn hình.
library;

import 'package:balance/features/journal/domain/journal_entry.dart';

/// Số cột của lưới — tuần bắt đầu từ Thứ Hai như lịch Việt Nam.
const int daysPerWeek = 7;

/// Khoá gom nhóm theo ngày, bỏ phần giờ.
class DayKey implements Comparable<DayKey> {
  const DayKey(this.year, this.month, this.day);

  factory DayKey.from(DateTime moment) =>
      DayKey(moment.year, moment.month, moment.day);

  final int year;
  final int month;
  final int day;

  DateTime toDateTime() => DateTime(year, month, day);

  @override
  bool operator ==(Object other) =>
      other is DayKey &&
      other.year == year &&
      other.month == month &&
      other.day == day;

  @override
  int get hashCode => Object.hash(year, month, day);

  @override
  int compareTo(DayKey other) => toDateTime().compareTo(other.toDateTime());

  @override
  String toString() => '$year-$month-$day';
}

/// Các ô của lưới tháng: ``null`` là ô trống chèn trước ngày 1.
///
/// Ví dụ tháng bắt đầu vào Chủ Nhật thì có 6 ô trống đứng trước, để ngày 1
/// rơi đúng cột CN.
List<DateTime?> monthGridDays(DateTime month) {
  final first = DateTime(month.year, month.month);
  // DateTime.weekday: Thứ Hai = 1 ... Chủ Nhật = 7 → số ô trống là weekday-1.
  final leadingBlanks = first.weekday - 1;
  final dayCount = DateTime(month.year, month.month + 1, 0).day;
  return [
    ...List<DateTime?>.filled(leadingBlanks, null),
    for (var day = 1; day <= dayCount; day++)
      DateTime(month.year, month.month, day),
  ];
}

/// Gom bữa ăn theo ngày, mỗi ngày sắp theo thời điểm ăn tăng dần.
Map<DayKey, List<JournalEntry>> entriesByDay(Iterable<JournalEntry> entries) {
  final grouped = <DayKey, List<JournalEntry>>{};
  for (final entry in entries) {
    grouped.putIfAbsent(DayKey.from(entry.loggedAt), () => []).add(entry);
  }
  for (final list in grouped.values) {
    list.sort((left, right) => left.loggedAt.compareTo(right.loggedAt));
  }
  return grouped;
}

/// Bữa ăn được chọn làm sticker đại diện cho một ngày.
///
/// Ưu tiên bữa đầu tiên CÓ sticker; cả ngày không có sticker nào thì trả bữa
/// đầu tiên để ô lịch vẫn hiện được tên món.
JournalEntry? representativeEntry(List<JournalEntry> dayEntries) {
  if (dayEntries.isEmpty) return null;
  for (final entry in dayEntries) {
    final path = entry.stickerPath;
    if (path != null && path.isNotEmpty) return entry;
  }
  return dayEntries.first;
}

/// Món xuất hiện nhiều nhất kèm số lần, dùng cho thẻ "Phổ biến nhất".
({String dishName, int count})? mostFrequentDish(
  Iterable<JournalEntry> entries,
) {
  final counts = <String, int>{};
  for (final entry in entries) {
    counts[entry.dishName] = (counts[entry.dishName] ?? 0) + 1;
  }
  if (counts.isEmpty) return null;
  final best = counts.entries.reduce(
    // So sánh chặt (>) nên khi hoà, món gặp trước thắng — kết quả ổn định
    // thay vì nhảy lung tung mỗi lần dựng lại.
    (current, next) => next.value > current.value ? next : current,
  );
  return (dishName: best.key, count: best.value);
}
