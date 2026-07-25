import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
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
    expect(find.text('Bún bò Huế'), findsOneWidget);
    expect(find.text('534 kcal'), findsOneWidget);
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
