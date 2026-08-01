import 'dart:io';

import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/presentation/month_summary.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:balance/features/journal/presentation/sticker_calendar.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
  testWidgets(
    'journal keeps the monthly sticker art and calendar with daily details',
    (tester) async {
      final state = AppState.memory();
      final now = DateTime(2026, 7, 30, 12);
      StickerPaths.directory = Directory('assets/food').absolute.path;
      addTearDown(() => StickerPaths.directory = null);
      await state.addJournalEntry(
        JournalEntry(
          id: 'calendar-com-tam',
          dishName: 'Cơm tấm',
          loggedAt: now,
          mealType: MealType.lunch,
          calories: 650,
          proteinGrams: 32,
          fatGrams: 22,
          carbsGrams: 78,
          fiberGrams: 4,
          totalGrams: 370,
          stickerPath: 'com-tam.png',
        ),
      );

      await tester.pumpWidget(
        AppScope(
          notifier: state,
          child: MaterialApp(
            theme: BalanceTheme.light,
            home: JournalScreen(now: now),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.byType(MonthStickerPile), findsOneWidget);
      expect(find.byType(StickerCalendar), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Tổng quan ngày'),
        220,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Tổng quan ngày'), findsOneWidget);
      await tester.scrollUntilVisible(
        find.text('Bữa ăn'),
        180,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Bữa ăn'), findsOneWidget);
      expect(find.text('Thêm món'), findsOneWidget);
    },
  );

  testWidgets('analysis result can be saved once and appears in journal', (
    tester,
  ) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await state.signIn(email: 'an@example.com', password: 'matkhau123');
    await state.completeProfile(_profile);
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Bún bò Huế',
      'source': 'vision',
      'nutrition': {
        'total_calories': 534,
        'total_protein_g': 28,
        'total_fat_g': 17,
        'total_carbs_g': 67,
        'total_fiber_g': 3.5,
        'total_grams': 520,
      },
      'dishes': <Object>[],
    });

    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: AnalysisResultScreen(result: result),
        ),
      ),
    );

    await tester.ensureVisible(find.text('Thêm vào nhật ký'));
    await tester.tap(find.text('Thêm vào nhật ký'));
    await tester.pumpAndSettle();
    expect(state.journalEntries, hasLength(1));
    expect(find.text('Đã lưu vào nhật ký'), findsOneWidget);

    await tester.tap(find.text('Đã lưu vào nhật ký'));
    await tester.pump();
    expect(state.journalEntries, hasLength(1));

    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: const JournalScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    // Lịch tháng chiếm phần trên nên thẻ bữa ăn nằm dưới tầm nhìn; ListView
    // dựng lười nên phải cuộn tới thì widget mới tồn tại.
    await tester.scrollUntilVisible(
      find.text('Bún bò Huế'),
      200,
      scrollable: find.byType(Scrollable).first,
    );
    // Tên món có thể xuất hiện thêm lần nữa trong thẻ "Phổ biến nhất" của
    // phần tổng kết tháng, nên không đòi đúng-một.
    expect(find.text('Bún bò Huế'), findsWidgets);
    expect(find.text('534 kcal'), findsOneWidget);
  });

  testWidgets('swiping a journal entry offers undo before it is permanent', (
    tester,
  ) async {
    final state = AppState.memory();
    final now = DateTime(2026, 7, 30, 12);
    final entry = JournalEntry(
      id: 'undo-bun-cha',
      dishName: 'Bún chả',
      loggedAt: now,
      mealType: MealType.lunch,
      calories: 550,
      proteinGrams: 25,
      fatGrams: 20,
      carbsGrams: 65,
      fiberGrams: 3,
      totalGrams: 400,
    );
    await state.addJournalEntry(entry);

    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: JournalScreen(now: now),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.byKey(const ValueKey('undo-bun-cha')),
      220,
      scrollable: find.byType(Scrollable).first,
    );
    final gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const ValueKey('undo-bun-cha'))),
    );
    await gesture.moveBy(const Offset(-30, 0));
    await tester.pump();
    await gesture.moveBy(const Offset(-130, 0));
    await tester.pump(const Duration(milliseconds: 100));
    expect(
      find.byKey(const ValueKey('journal-delete-undo-bun-cha')),
      findsOneWidget,
    );
    await gesture.moveBy(const Offset(-370, 0));
    await gesture.up();
    await tester.pumpAndSettle();

    expect(find.text('Đã xoá Bún chả khỏi nhật ký'), findsOneWidget);
    expect(find.text('Hoàn tác'), findsOneWidget);
    await tester.tap(find.text('Hoàn tác'));
    await tester.pumpAndSettle();
    expect(state.journalEntries.single.id, 'undo-bun-cha');
  });
}

const _profile = UserProfile(
  name: 'An',
  email: 'an@example.com',
  age: 25,
  heightCm: 170,
  weightKg: 65,
  targetWeightKg: 60,
  gender: 'Nam',
  activity: 'Vừa phải',
  goal: 'Giảm cân',
);
