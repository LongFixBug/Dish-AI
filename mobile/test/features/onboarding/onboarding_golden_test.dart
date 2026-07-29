@Tags(['golden'])
library;

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    final font = FontLoader('Baloo 2')
      ..addFont(rootBundle.load('assets/fonts/Baloo2-Variable.ttf'));
    await font.load();
  });

  testWidgets('profile setup matches the approved first step', (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(_testApp(const ProfileSetupScreen()));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(ProfileSetupScreen),
      matchesGoldenFile('goldens/profile_setup_step1.png'),
    );

    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(ProfileSetupScreen),
      matchesGoldenFile('goldens/profile_setup_step2.png'),
    );

    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(ProfileSetupScreen),
      matchesGoldenFile('goldens/profile_setup_step3.png'),
    );

    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(ProfileSetupScreen),
      matchesGoldenFile('goldens/profile_setup_step4.png'),
    );
  });

  testWidgets('dashboard includes the approved bottom navigation', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      AppScope(
        notifier: AppState.memory(),
        child: _testApp(MainShell(now: DateTime(2026, 5, 15, 9))),
      ),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(MainShell),
      matchesGoldenFile('goldens/dashboard.png'),
    );
  });
}

Widget _testApp(Widget home) {
  return MaterialApp(theme: BalanceTheme.light, home: home);
}
