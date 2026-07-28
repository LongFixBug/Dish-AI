import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/domain/month_grid.dart';
import 'package:flutter_test/flutter_test.dart';

JournalEntry _entry({
  required String id,
  required DateTime loggedAt,
  String dishName = 'Cơm tấm',
  String? stickerPath,
}) => JournalEntry(
  id: id,
  dishName: dishName,
  loggedAt: loggedAt,
  mealType: MealType.lunch,
  calories: 500,
  proteinGrams: 20,
  fatGrams: 15,
  carbsGrams: 60,
  fiberGrams: 3,
  totalGrams: 300,
  stickerPath: stickerPath,
);

void main() {
  group('monthGridDays', () {
    test('chèn đúng số ô trống để ngày 1 rơi vào cột của nó', () {
      // 1/2/2026 là Chủ Nhật → đứng cuối hàng, trước nó 6 ô trống.
      final grid = monthGridDays(DateTime(2026, 2));

      expect(DateTime(2026, 2).weekday, DateTime.sunday);
      expect(grid.take(6), everyElement(isNull));
      expect(grid[6], DateTime(2026, 2, 1));
    });

    test('tháng bắt đầu vào Thứ Hai thì không có ô trống nào', () {
      // 1/6/2026 là Thứ Hai.
      final grid = monthGridDays(DateTime(2026, 6));

      expect(DateTime(2026, 6).weekday, DateTime.monday);
      expect(grid.first, DateTime(2026, 6, 1));
    });

    test('đếm đủ số ngày của tháng, kể cả tháng 2 năm nhuận', () {
      expect(
        monthGridDays(DateTime(2026, 2)).whereType<DateTime>(),
        hasLength(28),
      );
      expect(
        monthGridDays(DateTime(2024, 2)).whereType<DateTime>(),
        hasLength(29),
      );
      expect(
        monthGridDays(DateTime(2026, 7)).whereType<DateTime>(),
        hasLength(31),
      );
      expect(
        monthGridDays(DateTime(2026, 4)).whereType<DateTime>(),
        hasLength(30),
      );
    });

    test('tháng 12 không tràn sang năm sau khi tính số ngày', () {
      expect(
        monthGridDays(DateTime(2026, 12)).whereType<DateTime>(),
        hasLength(31),
      );
    });
  });

  group('entriesByDay', () {
    test('gom theo ngày và bỏ qua phần giờ', () {
      final grouped = entriesByDay([
        _entry(id: 'a', loggedAt: DateTime(2026, 7, 27, 8)),
        _entry(id: 'b', loggedAt: DateTime(2026, 7, 27, 19)),
        _entry(id: 'c', loggedAt: DateTime(2026, 7, 28, 12)),
      ]);

      expect(grouped[const DayKey(2026, 7, 27)], hasLength(2));
      expect(grouped[const DayKey(2026, 7, 28)], hasLength(1));
    });

    test('trong một ngày thì sắp theo giờ ăn tăng dần', () {
      final grouped = entriesByDay([
        _entry(id: 'toi', loggedAt: DateTime(2026, 7, 27, 19)),
        _entry(id: 'sang', loggedAt: DateTime(2026, 7, 27, 7)),
      ]);

      expect(grouped[const DayKey(2026, 7, 27)]!.map((entry) => entry.id), [
        'sang',
        'toi',
      ]);
    });
  });

  group('representativeEntry', () {
    test('ưu tiên bữa đầu tiên có sticker', () {
      final chosen = representativeEntry([
        _entry(id: 'khong-anh', loggedAt: DateTime(2026, 7, 27, 7)),
        _entry(
          id: 'co-anh',
          loggedAt: DateTime(2026, 7, 27, 12),
          stickerPath: '/tmp/a.png',
        ),
      ]);

      expect(chosen?.id, 'co-anh');
    });

    test('cả ngày không có sticker thì lấy bữa đầu tiên', () {
      final chosen = representativeEntry([
        _entry(id: 'dau', loggedAt: DateTime(2026, 7, 27, 7)),
        _entry(id: 'sau', loggedAt: DateTime(2026, 7, 27, 12)),
      ]);

      expect(chosen?.id, 'dau');
    });

    test('ngày trống trả null', () {
      expect(representativeEntry(const []), isNull);
    });
  });

  group('mostFrequentDish', () {
    test('trả món nhiều lần nhất kèm số lần', () {
      final top = mostFrequentDish([
        _entry(id: '1', loggedAt: DateTime(2026, 7, 1), dishName: 'Phở'),
        _entry(id: '2', loggedAt: DateTime(2026, 7, 2), dishName: 'Cơm tấm'),
        _entry(id: '3', loggedAt: DateTime(2026, 7, 3), dishName: 'Phở'),
      ]);

      expect(top?.dishName, 'Phở');
      expect(top?.count, 2);
    });

    test('hoà nhau thì món gặp trước thắng, kết quả không nhảy', () {
      final entries = [
        _entry(id: '1', loggedAt: DateTime(2026, 7, 1), dishName: 'Phở'),
        _entry(id: '2', loggedAt: DateTime(2026, 7, 2), dishName: 'Bún'),
      ];

      expect(mostFrequentDish(entries)?.dishName, 'Phở');
      expect(mostFrequentDish(entries)?.dishName, 'Phở');
    });

    test('chưa ăn gì thì trả null', () {
      expect(mostFrequentDish(const []), isNull);
    });
  });
}
