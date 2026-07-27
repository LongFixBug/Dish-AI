import 'dart:io';
import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/presentation/sticker_calendar.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

JournalEntry _entry(String id, DateTime loggedAt, {String? dishName}) =>
    JournalEntry(
      id: id,
      dishName: dishName ?? 'Cơm tấm',
      loggedAt: loggedAt,
      mealType: MealType.lunch,
      calories: 500,
      proteinGrams: 20,
      fatGrams: 15,
      carbsGrams: 60,
      fiberGrams: 3,
      totalGrams: 300,
    );

Widget _app(Widget child) =>
    MaterialApp(theme: BalanceTheme.light, home: Scaffold(body: child));

void main() {
  testWidgets('lưới hiện đủ ngày trong tháng và nhãn thứ', (tester) async {
    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 2),
            entries: const [],
            today: DateTime(2026, 2, 27),
          ),
        ),
      ),
    );

    expect(find.text('Tháng 2, 2026'), findsOneWidget);
    expect(find.text('T2'), findsOneWidget);
    expect(find.text('CN'), findsOneWidget);
    expect(find.text('1'), findsOneWidget);
    expect(find.text('28'), findsOneWidget);
    expect(find.text('29'), findsNothing, reason: '2026 không phải năm nhuận');
  });

  testWidgets('ngày nhiều món hiện badge số lượng', (tester) async {
    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 7),
            entries: [
              _entry('a', DateTime(2026, 7, 10, 8)),
              _entry('b', DateTime(2026, 7, 10, 12)),
              _entry('c', DateTime(2026, 7, 10, 19)),
              _entry('d', DateTime(2026, 7, 11, 12)),
            ],
            today: DateTime(2026, 7, 27),
          ),
        ),
      ),
    );

    expect(find.text('×3'), findsOneWidget);
    expect(find.text('×1'), findsNothing, reason: 'một món thì không cần badge');
  });

  testWidgets('bấm vào ô ngày báo đúng ngày đó', (tester) async {
    DateTime? tapped;
    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 7),
            entries: [_entry('a', DateTime(2026, 7, 15, 12))],
            today: DateTime(2026, 7, 27),
            onDayTap: (day) => tapped = day,
          ),
        ),
      ),
    );

    await tester.tap(find.text('15'));
    await tester.pumpAndSettle();

    expect(tapped, DateTime(2026, 7, 15));
  });

  testWidgets('mũi tên đổi tháng đi đúng chiều, không tràn năm', (
    tester,
  ) async {
    final months = <DateTime>[];
    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 1),
            entries: const [],
            today: DateTime(2026, 1, 5),
            onMonthChanged: months.add,
          ),
        ),
      ),
    );

    await tester.tap(find.bySemanticsLabel('Tháng trước'));
    await tester.pumpAndSettle();
    await tester.tap(find.bySemanticsLabel('Tháng sau'));
    await tester.pumpAndSettle();

    expect(months, [DateTime(2025, 12), DateTime(2026, 2)]);
  });

  testWidgets('ô ngày có sticker thì vẽ đúng ảnh đó', (tester) async {
    // IO đồng bộ: thân testWidgets chạy trong FakeAsync nên IO async thật
    // sẽ treo vĩnh viễn.
    final temp = Directory.systemTemp.createTempSync('calendar-sticker');
    StickerPaths.directory = temp.path;
    addTearDown(() {
      StickerPaths.directory = null;
      temp.deleteSync(recursive: true);
    });
    File('${temp.path}/com-tam.png').writeAsBytesSync(_tinyPng);

    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 7),
            entries: [
              JournalEntry(
                id: 'a',
                dishName: 'Cơm tấm',
                loggedAt: DateTime(2026, 7, 15, 12),
                mealType: MealType.lunch,
                calories: 500,
                proteinGrams: 20,
                fatGrams: 15,
                carbsGrams: 60,
                fiberGrams: 3,
                totalGrams: 300,
                stickerPath: 'com-tam.png',
              ),
            ],
            today: DateTime(2026, 7, 27),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(Image), findsOneWidget);
  });

  testWidgets('ngày nhiều món vừa có sticker vừa có badge', (tester) async {
    final temp = Directory.systemTemp.createTempSync('calendar-sticker-multi');
    StickerPaths.directory = temp.path;
    addTearDown(() {
      StickerPaths.directory = null;
      temp.deleteSync(recursive: true);
    });
    File('${temp.path}/pho.png').writeAsBytesSync(_tinyPng);

    JournalEntry make(String id, int hour, {String? sticker}) => JournalEntry(
      id: id,
      dishName: 'Phở',
      loggedAt: DateTime(2026, 7, 15, hour),
      mealType: MealType.lunch,
      calories: 400,
      proteinGrams: 20,
      fatGrams: 10,
      carbsGrams: 50,
      fiberGrams: 2,
      totalGrams: 400,
      stickerPath: sticker,
    );

    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 7),
            entries: [
              make('a', 7),
              make('b', 12, sticker: 'pho.png'),
              make('c', 19),
            ],
            today: DateTime(2026, 7, 27),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(Image), findsOneWidget, reason: 'sticker phải hiện');
    expect(find.text('×3'), findsOneWidget, reason: 'badge phải hiện');
  });

  testWidgets('nhiều món có sticker thì xòe ra hết, không chỉ một hình', (
    tester,
  ) async {
    final temp = Directory.systemTemp.createTempSync('calendar-fan');
    StickerPaths.directory = temp.path;
    addTearDown(() {
      StickerPaths.directory = null;
      temp.deleteSync(recursive: true);
    });
    for (final name in ['a', 'b', 'c']) {
      File('${temp.path}/$name.png').writeAsBytesSync(_tinyPng);
    }

    JournalEntry make(String id, int hour, String sticker) => JournalEntry(
      id: id,
      dishName: 'Món $id',
      loggedAt: DateTime(2026, 7, 15, hour),
      mealType: MealType.lunch,
      calories: 400,
      proteinGrams: 20,
      fatGrams: 10,
      carbsGrams: 50,
      fiberGrams: 2,
      totalGrams: 400,
      stickerPath: sticker,
    );

    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 7),
            entries: [
              make('a', 7, 'a.png'),
              make('b', 12, 'b.png'),
              make('c', 19, 'c.png'),
            ],
            today: DateTime(2026, 7, 27),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(Image), findsNWidgets(3));
    expect(find.text('×3'), findsOneWidget);
  });

  testWidgets('quá ba món thì chỉ xòe ba lá, phần dư để badge kể', (
    tester,
  ) async {
    final temp = Directory.systemTemp.createTempSync('calendar-fan-max');
    StickerPaths.directory = temp.path;
    addTearDown(() {
      StickerPaths.directory = null;
      temp.deleteSync(recursive: true);
    });
    for (var i = 0; i < 5; i++) {
      File('${temp.path}/s$i.png').writeAsBytesSync(_tinyPng);
    }

    await tester.pumpWidget(
      _app(
        SingleChildScrollView(
          child: StickerCalendar(
            month: DateTime(2026, 7),
            entries: [
              for (var i = 0; i < 5; i++)
                JournalEntry(
                  id: 's$i',
                  dishName: 'Món $i',
                  loggedAt: DateTime(2026, 7, 15, 7 + i),
                  mealType: MealType.lunch,
                  calories: 300,
                  proteinGrams: 10,
                  fatGrams: 5,
                  carbsGrams: 40,
                  fiberGrams: 1,
                  totalGrams: 250,
                  stickerPath: 's$i.png',
                ),
            ],
            today: DateTime(2026, 7, 27),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.byType(Image), findsNWidgets(3));
    expect(find.text('×5'), findsOneWidget);
  });
}

// PNG 1x1 hợp lệ để Image.file giải mã được.
final Uint8List _tinyPng = Uint8List.fromList([
  0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D,
  0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
  0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4, 0x89, 0x00, 0x00, 0x00,
  0x0D, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9C, 0x62, 0x00, 0x01, 0x00, 0x00,
  0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49,
  0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
]);
