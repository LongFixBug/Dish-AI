import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('shows dinner budget, meal cards, preferences and menu action', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(theme: BalanceTheme.light, home: const SuggestionsScreen()),
    );

    expect(find.text('Gợi ý bữa tối'), findsOneWidget);
    expect(find.text('560 kcal hôm nay'), findsOneWidget);
    expect(find.text('Cá kho tộ + cơm'), findsOneWidget);
    expect(find.text('520 kcal'), findsOneWidget);
    expect(find.text('Bún gà rau củ'), findsOneWidget);
    expect(find.text('480 kcal'), findsOneWidget);
    expect(find.text('Nhiều đạm'), findsOneWidget);
    expect(find.text('Ít dầu'), findsOneWidget);
    expect(find.text('Món Việt'), findsOneWidget);
    expect(find.text('Xem thực đơn'), findsOneWidget);
  });

  testWidgets('preferences can be changed and are persisted in app state', (
    tester,
  ) async {
    final state = await AppState.restore(MemoryAppStorage());
    await state.signIn(email: _profile.email);
    await state.completeProfile(_profile);
    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: const SuggestionsScreen(),
        ),
      ),
    );

    await tester.ensureVisible(find.text('Chỉnh sửa'));
    await tester.tap(find.text('Chỉnh sửa'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(CheckboxListTile, 'Ít dầu'));
    await tester.tap(find.text('Lưu sở thích'));
    await tester.pumpAndSettle();

    expect(state.preferences, isNot(contains('Ít dầu')));
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
