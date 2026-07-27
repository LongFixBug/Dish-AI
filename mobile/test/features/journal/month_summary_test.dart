import 'dart:io';
import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/presentation/month_summary.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

JournalEntry _entry({
  required String id,
  required DateTime loggedAt,
  double calories = 500,
  String dishName = 'Cơm tấm',
  String? stickerPath,
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
  stickerPath: stickerPath,
);

Widget _app(Widget child) => MaterialApp(
  theme: BalanceTheme.light,
  home: Scaffold(body: SingleChildScrollView(child: child)),
);

// PNG 1x1 hợp lệ để Image.file giải mã được trong test.
final Uint8List _tinyPng = Uint8List.fromList([
  0x89,
  0x50,
  0x4E,
  0x47,
  0x0D,
  0x0A,
  0x1A,
  0x0A,
  0x00,
  0x00,
  0x00,
  0x0D,
  0x49,
  0x48,
  0x44,
  0x52,
  0x00,
  0x00,
  0x00,
  0x01,
  0x00,
  0x00,
  0x00,
  0x01,
  0x08,
  0x06,
  0x00,
  0x00,
  0x00,
  0x1F,
  0x15,
  0xC4,
  0x89,
  0x00,
  0x00,
  0x00,
  0x0D,
  0x49,
  0x44,
  0x41,
  0x54,
  0x78,
  0x9C,
  0x62,
  0x00,
  0x01,
  0x00,
  0x00,
  0x05,
  0x00,
  0x01,
  0x0D,
  0x0A,
  0x2D,
  0xB4,
  0x00,
  0x00,
  0x00,
  0x00,
  0x49,
  0x45,
  0x4E,
  0x44,
  0xAE,
  0x42,
  0x60,
  0x82,
]);

void main() {
  late Directory temp;

  // IO đồng bộ CÓ CHỦ ĐÍCH: thân testWidgets chạy trong FakeAsync, nên IO
  // bất đồng bộ thật sẽ không bao giờ hoàn thành — test treo im lặng và kéo
  // cả suite đứng theo. Bản sync không đi qua event loop nên miễn nhiễm.
  setUp(() {
    temp = Directory.systemTemp.createTempSync('month-summary-test');
    // Nhật ký chỉ lưu TÊN file; thư mục thật do lần chạy hiện tại quyết định.
    StickerPaths.directory = temp.path;
  });

  tearDown(() {
    StickerPaths.directory = null;
    if (temp.existsSync()) temp.deleteSync(recursive: true);
  });

  /// Ghi file và trả về TÊN file, đúng như kho sticker thật trả về.
  String writeSticker(String name) {
    File('${temp.path}/$name.png').writeAsBytesSync(_tinyPng);
    return '$name.png';
  }

  group('MonthStickerPile', () {
    testWidgets(
      'tháng không có sticker nào thì ẩn hẳn, không chừa khung trống',
      (tester) async {
        await tester.pumpWidget(
          _app(
            MonthStickerPile(
              month: DateTime(2026, 7),
              animate: false,
              entries: [_entry(id: 'a', loggedAt: DateTime(2026, 7, 1))],
            ),
          ),
        );

        expect(find.byType(Image), findsNothing);
        expect(find.textContaining('món tháng này'), findsNothing);
      },
    );

    testWidgets('có sticker thì hiện đống ảnh kèm nhãn đếm', (tester) async {
      final path = writeSticker('com-tam');
      await tester.pumpWidget(
        _app(
          MonthStickerPile(
            // animate: false → khung hình đầu đã là trạng thái đã rơi xong.
            month: DateTime(2026, 7),
            animate: false,
            entries: [
              _entry(
                id: 'a',
                loggedAt: DateTime(2026, 7, 1),
                stickerPath: path,
              ),
              _entry(id: 'b', loggedAt: DateTime(2026, 7, 2)),
            ],
          ),
        ),
      );
      await tester.pump();

      expect(find.byType(Image), findsOneWidget);
      expect(find.text('2 món tháng này'), findsOneWidget);
    });
  });

  group('MonthStatsSection', () {
    testWidgets('tháng trống hiện lời nhắn thay vì số 0 vô hồn', (
      tester,
    ) async {
      await tester.pumpWidget(
        _app(MonthStatsSection(month: DateTime(2026, 7), entries: const [])),
      );

      expect(find.textContaining('Chưa có món nào'), findsOneWidget);
      expect(find.text('Tổng món'), findsNothing);
    });

    testWidgets('hiện đủ ba ô số liệu, món phổ biến và biểu đồ tuần', (
      tester,
    ) async {
      await tester.pumpWidget(
        _app(
          MonthStatsSection(
            month: DateTime(2026, 7),
            entries: [
              _entry(
                id: 'a',
                loggedAt: DateTime(2026, 7, 1),
                calories: 600,
                dishName: 'Phở',
              ),
              _entry(
                id: 'b',
                loggedAt: DateTime(2026, 7, 2),
                calories: 400,
                dishName: 'Phở',
              ),
              _entry(
                id: 'c',
                loggedAt: DateTime(2026, 7, 9),
                calories: 500,
                dishName: 'Cơm tấm',
              ),
            ],
          ),
        ),
      );

      expect(find.text('Tổng món'), findsOneWidget);
      expect(find.text('3', skipOffstage: false), findsWidgets);
      expect(find.text('Tổng kcal'), findsOneWidget);
      expect(find.text('1500'), findsOneWidget);
      expect(find.text('TB/món'), findsOneWidget);
      expect(find.text('Phổ biến nhất'), findsOneWidget);
      expect(find.text('Phở'), findsOneWidget);
      expect(find.text('×2'), findsOneWidget);
      expect(find.text('Món theo tuần'), findsOneWidget);
      expect(find.text('Tuần 1'), findsOneWidget);
      expect(find.text('Tuần 5'), findsOneWidget);
    });

    testWidgets('tổng kcal lớn được rút gọn thành dạng k', (tester) async {
      await tester.pumpWidget(
        _app(
          MonthStatsSection(
            month: DateTime(2026, 7),
            entries: [
              for (var day = 1; day <= 25; day++)
                _entry(
                  id: 'e$day',
                  loggedAt: DateTime(2026, 7, day),
                  calories: 800,
                ),
            ],
          ),
        ),
      );

      // 25 × 800 = 20.000 kcal → hiện "20.0k" thay vì con số dài.
      expect(find.text('20.0k'), findsOneWidget);
    });

    testWidgets('mỗi món ăn đúng một lần thì ẩn thẻ "Phổ biến nhất"', (
      tester,
    ) async {
      await tester.pumpWidget(
        _app(
          MonthStatsSection(
            month: DateTime(2026, 7),
            entries: [
              _entry(id: 'a', loggedAt: DateTime(2026, 7, 1), dishName: 'Phở'),
              _entry(id: 'b', loggedAt: DateTime(2026, 7, 2), dishName: 'Bún'),
            ],
          ),
        ),
      );

      expect(find.text('Phổ biến nhất'), findsNothing);
      // Các thẻ số liệu khác vẫn hiện bình thường.
      expect(find.text('Tổng món'), findsOneWidget);
    });
  });
}
