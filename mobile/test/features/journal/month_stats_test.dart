import 'dart:math';

import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/domain/month_stats.dart';
import 'package:flutter_test/flutter_test.dart';

JournalEntry _entry({
  required String id,
  required DateTime loggedAt,
  double calories = 500,
  String dishName = 'Cơm tấm',
}) => JournalEntry(
  id: id,
  dishName: dishName,
  loggedAt: loggedAt,
  mealType: MealType.lunch,
  calories: calories,
  proteinGrams: 20,
  fatGrams: 15,
  carbsGrams: 60,
  fiberGrams: 3,
  totalGrams: 300,
);

void main() {
  group('entriesInMonth', () {
    test('chỉ giữ bữa ăn thuộc đúng tháng, đúng năm', () {
      final picked = entriesInMonth([
        _entry(id: 'trong', loggedAt: DateTime(2026, 7, 15)),
        _entry(id: 'thang-khac', loggedAt: DateTime(2026, 6, 30)),
        _entry(id: 'nam-khac', loggedAt: DateTime(2025, 7, 15)),
      ], DateTime(2026, 7));

      expect(picked.map((entry) => entry.id), ['trong']);
    });
  });

  group('monthTotals', () {
    test('cộng đúng tổng món, tổng kcal và trung bình', () {
      final totals = monthTotals([
        _entry(id: 'a', loggedAt: DateTime(2026, 7, 1), calories: 600),
        _entry(id: 'b', loggedAt: DateTime(2026, 7, 2), calories: 400),
      ]);

      expect(totals.totalMeals, 2);
      expect(totals.totalCalories, 1000);
      expect(totals.averageCalories, 500);
    });

    test('tháng trống thì trung bình là 0, không chia cho 0', () {
      final totals = monthTotals(const []);

      expect(totals.totalMeals, 0);
      expect(totals.averageCalories, 0);
    });
  });

  group('entriesInYear and yearTotals', () {
    test('lọc đúng năm và cộng cả các tháng khác nhau', () {
      final entries = [
        _entry(id: 'a', loggedAt: DateTime(2026, 1, 2), calories: 600),
        _entry(id: 'b', loggedAt: DateTime(2026, 12, 31), calories: 400),
        _entry(id: 'c', loggedAt: DateTime(2025, 12, 31), calories: 900),
      ];

      expect(entriesInYear(entries, 2026).map((entry) => entry.id), ['a', 'b']);
      expect(yearTotals(entriesInYear(entries, 2026)).totalMeals, 2);
      expect(yearTotals(entriesInYear(entries, 2026)).totalCalories, 1000);
    });
  });

  group('weeklyMealCounts', () {
    test('ngày 1-7 vào tuần 1, ngày 8 sang tuần 2, ngày 29+ vào tuần 5', () {
      final counts = weeklyMealCounts(DateTime(2026, 7), [
        _entry(id: 'a', loggedAt: DateTime(2026, 7, 1)),
        _entry(id: 'b', loggedAt: DateTime(2026, 7, 7)),
        _entry(id: 'c', loggedAt: DateTime(2026, 7, 8)),
        _entry(id: 'd', loggedAt: DateTime(2026, 7, 31)),
      ]);

      expect(counts, [2, 1, 0, 0, 1]);
    });

    test('tháng 28 ngày ra đúng 4 tuần', () {
      expect(weeklyMealCounts(DateTime(2026, 2), const []), hasLength(4));
    });

    test('bữa ăn tháng khác không lọt vào cột nào', () {
      final counts = weeklyMealCounts(DateTime(2026, 7), [
        _entry(id: 'khac', loggedAt: DateTime(2026, 6, 3)),
      ]);

      expect(counts.every((value) => value == 0), isTrue);
    });
  });

  group('pileSeed', () {
    test('hai tháng khác nhau ra seed khác nhau', () {
      expect(pileSeed(DateTime(2026, 7)), isNot(pileSeed(DateTime(2026, 8))));
      expect(pileSeed(DateTime(2026, 12)), isNot(pileSeed(DateTime(2027, 1))));
    });
  });

  group('dropStickers', () {
    test('sticker đầu tiên nằm sát đáy khung', () {
      final dropped = dropStickers(
        count: 1,
        seed: 1,
        width: 300,
        height: 200,
        baseSize: 60,
      );

      final first = dropped.single;
      // Đáy sticker chạm mép dưới và thò xuống một chút: khung cắt ngang hàng
      // dưới cùng, đúng kiểu đống đồ thật chứ không phải hàng xếp ngay ngắn.
      final bottom = first.top + first.size;
      expect(bottom, greaterThan(200));
      expect(bottom - 200, lessThan(first.size * 0.25));
    });

    test('sticker sau đáp LÊN TRÊN sticker trước khi cùng cột', () {
      // Nhiều sticker trong khung hẹp thì buộc phải chồng lên nhau.
      final dropped = dropStickers(
        count: 8,
        seed: 3,
        width: 120,
        height: 400,
        baseSize: 60,
      );

      final tops = dropped.map((item) => item.top).toList()..sort();
      // Có ít nhất một sticker nằm cao hơn hẳn cái thấp nhất → đống có chiều cao.
      expect(tops.first, lessThan(tops.last - 20));
    });

    test('không sticker nào tràn ra ngoài hai mép ngang', () {
      final dropped = dropStickers(count: 40, seed: 9, width: 320, height: 180);

      for (final item in dropped) {
        expect(item.left, greaterThanOrEqualTo(0));
        expect(item.left + item.size, lessThanOrEqualTo(320 + 14));
      }
    });

    test('đống cao quá khung vẫn bị ghim trong tầm nhìn', () {
      final dropped = dropStickers(count: 60, seed: 5, width: 100, height: 120);

      expect(dropped.every((item) => item.top >= 0), isTrue);
    });

    test('cùng seed cho đúng một đống — vào lại trang không xáo trộn', () {
      final first = dropStickers(
        count: 15,
        seed: 202607,
        width: 300,
        height: 180,
      );
      final second = dropStickers(
        count: 15,
        seed: 202607,
        width: 300,
        height: 180,
      );

      for (var i = 0; i < first.length; i++) {
        expect(first[i].left, second[i].left);
        expect(first[i].top, second[i].top);
        expect(first[i].size, second[i].size);
        expect(first[i].angle, second[i].angle);
      }
    });

    test('khung chưa đo được kích thước thì trả rỗng, không chia cho 0', () {
      expect(dropStickers(count: 5, seed: 1, width: 0, height: 100), isEmpty);
      expect(dropStickers(count: 0, seed: 1, width: 100, height: 100), isEmpty);
    });
  });

  group('fillingStickerSize', () {
    test('ít món thì sticker to ra để đống không trống khung', () {
      final few = fillingStickerSize(count: 3, width: 320, height: 180);
      final many = fillingStickerSize(count: 30, width: 320, height: 180);

      expect(few, greaterThan(many));
    });

    test('luôn nằm trong biên: không bé như hạt đỗ, không tràn khung', () {
      for (final count in [1, 3, 10, 30, 200]) {
        final size = fillingStickerSize(count: count, width: 320, height: 180);
        expect(size, inInclusiveRange(40, 104));
      }
    });

    test('đống ít món lấp được phần lớn chiều cao khung', () {
      final dropped = dropStickers(
        count: 3,
        seed: 202607,
        width: 320,
        height: 180,
      );

      final highest = dropped.map((item) => item.top).reduce(min);
      // Đỉnh đống phải vượt quá nửa khung tính từ đáy lên.
      expect(highest, lessThan(180 * 0.55));
    });
  });
}
