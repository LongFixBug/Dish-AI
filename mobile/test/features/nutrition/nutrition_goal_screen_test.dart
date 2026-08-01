import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/nutrition/presentation/nutrition_goal_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('nutrition retry state uses the app sketch controls', (
    tester,
  ) async {
    await tester.pumpWidget(
      AppScope(
        notifier: AppState.memory(),
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: const NutritionGoalScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Chưa tải được bảng nhu cầu dinh dưỡng.'), findsOneWidget);
    expect(find.byType(SketchCard), findsOneWidget);
    expect(find.byType(PressableButton), findsOneWidget);
    expect(find.byType(FilledButton), findsNothing);
  });
}
