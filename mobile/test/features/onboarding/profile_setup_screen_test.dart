import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/onboarding/presentation/onboarding_widgets.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'profile setup header explains that progress is a nutrition profile',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: BalanceTheme.light,
          home: Scaffold(
            body: OnboardingProgressHeader(
              step: 0,
              totalSteps: 4,
              onBack: () {},
            ),
          ),
        ),
      );

      expect(find.text('Hồ sơ dinh dưỡng'), findsOneWidget);
      expect(find.text('Bước 1 trong 4'), findsOneWidget);
    },
  );

  testWidgets('profile setup keeps the primary action visible on every step', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(theme: BalanceTheme.light, home: const ProfileSetupScreen()),
    );

    for (var step = 0; step < 4; step++) {
      final action = find.widgetWithText(
        PressableButton,
        step == 3 ? 'Hoàn tất' : 'Tiếp tục',
      );
      expect(tester.getBottomLeft(action).dy, lessThanOrEqualTo(844));
      if (step < 3) {
        await tester.tap(action);
        await tester.pumpAndSettle();
      }
    }
  });
}
