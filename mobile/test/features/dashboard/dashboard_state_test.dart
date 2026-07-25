import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/dashboard/presentation/dashboard_screen.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
  testWidgets('dashboard reflects profile and today journal totals', (
    tester,
  ) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await state.signIn(email: _profile.email, password: 'matkhau123');
    await state.completeProfile(_profile);
    await state.addJournalEntry(
      JournalEntry.fromAnalysis(
        result: _result,
        loggedAt: DateTime.now(),
        mealType: MealType.lunch,
      ),
    );

    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: const DashboardScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Chào bạn, An!'), findsOneWidget);
    expect(find.text('650'), findsOneWidget);
    expect(find.text('650 kcal'), findsOneWidget);

    await tester.tap(find.text('Nhật ký'));
    await tester.pumpAndSettle();
    expect(find.byType(JournalScreen), findsOneWidget);
    expect(find.text('Cơm tấm'), findsOneWidget);
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

final _result = AnalyzeResult.fromJson({
  'dish_name': 'Cơm tấm',
  'source': 'vision',
  'nutrition': {
    'total_calories': 650,
    'total_protein_g': 32,
    'total_fat_g': 22,
    'total_carbs_g': 78,
    'total_fiber_g': 4,
    'total_grams': 370,
  },
  'dishes': <Object>[],
});
