@Tags(['golden'])
library;

import 'dart:async';
import 'dart:io';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/load_test_fonts.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await loadBalanceTestFonts();
  });

  setUp(() {
    StickerPaths.directory = Directory('assets/food').absolute.path;
  });

  tearDown(() {
    StickerPaths.directory = null;
  });

  testWidgets('journal keeps the monthly sticker pile and calendar', (
    tester,
  ) async {
    await _setPhoneSize(tester);
    final state = await _journalState();
    await tester.pumpWidget(_app(state));
    await _precacheStickers(tester);

    await expectLater(
      find.byType(JournalScreen),
      matchesGoldenFile('goldens/journal_month.png'),
    );
  });

  testWidgets('journal daily overview follows the approved hierarchy', (
    tester,
  ) async {
    await _setPhoneSize(tester);
    final state = await _journalState();
    await tester.pumpWidget(_app(state));
    await _precacheStickers(tester);
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('journal-day-overview')),
      240,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pump(const Duration(milliseconds: 300));

    await expectLater(
      find.byType(JournalScreen),
      matchesGoldenFile('goldens/journal_day.png'),
    );
  });
}

Future<void> _setPhoneSize(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() => tester.binding.setSurfaceSize(null));
}

Widget _app(AppState state) {
  return AppScope(
    notifier: state,
    child: MaterialApp(
      theme: BalanceTheme.light,
      home: TickerMode(
        enabled: false,
        child: JournalScreen(
          now: DateTime(2026, 7, 30, 12),
          animateMonthPile: false,
        ),
      ),
    ),
  );
}

Future<void> _precacheStickers(WidgetTester tester) async {
  final context = tester.element(find.byType(JournalScreen));
  for (final name in ['com-tam.png', 'ca-kho.png', 'bun-ga.png']) {
    unawaited(
      precacheImage(
        FileImage(File('${StickerPaths.directory}/$name')),
        context,
      ),
    );
  }
  await tester.pump(const Duration(seconds: 2));
}

Future<AppState> _journalState() async {
  final state = AppState.memory();
  for (final entry in _entries) {
    await state.addJournalEntry(entry);
  }
  return state;
}

final _entries = [
  _entry(
    id: 'com-tam-30',
    dishName: 'Cơm tấm sườn',
    date: DateTime(2026, 7, 30, 8),
    mealType: MealType.breakfast,
    calories: 520,
    stickerPath: 'com-tam.png',
  ),
  _entry(
    id: 'ca-kho-30',
    dishName: 'Cá kho + rau luộc',
    date: DateTime(2026, 7, 30, 12),
    mealType: MealType.lunch,
    calories: 420,
    stickerPath: 'ca-kho.png',
  ),
  _entry(
    id: 'bun-ga-30',
    dishName: 'Bún gà',
    date: DateTime(2026, 7, 30, 19),
    mealType: MealType.dinner,
    calories: 340,
    stickerPath: 'bun-ga.png',
  ),
  _entry(
    id: 'com-tam-28',
    dishName: 'Cơm tấm',
    date: DateTime(2026, 7, 28, 12),
    mealType: MealType.lunch,
    calories: 610,
    stickerPath: 'com-tam.png',
  ),
  _entry(
    id: 'ca-kho-29',
    dishName: 'Cá kho',
    date: DateTime(2026, 7, 29, 12),
    mealType: MealType.lunch,
    calories: 430,
    stickerPath: 'ca-kho.png',
  ),
];

JournalEntry _entry({
  required String id,
  required String dishName,
  required DateTime date,
  required MealType mealType,
  required double calories,
  required String stickerPath,
}) {
  return JournalEntry(
    id: id,
    dishName: dishName,
    loggedAt: date,
    mealType: mealType,
    calories: calories,
    proteinGrams: 28,
    fatGrams: 16,
    carbsGrams: 58,
    fiberGrams: 4,
    totalGrams: 420,
    stickerPath: stickerPath,
  );
}
