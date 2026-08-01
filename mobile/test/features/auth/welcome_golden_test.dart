@Tags(['golden'])
library;

import 'package:balance/app.dart';
import 'package:balance/features/auth/presentation/welcome_screen.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/load_test_fonts.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await loadBalanceTestFonts();
  });

  testWidgets('welcome screen matches the approved visual baseline', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(const BalanceApp());
    final context = tester.element(find.byType(WelcomeScreen));
    await tester.runAsync(
      () => precacheImage(
        const AssetImage('assets/branding/balance-brand-board.png'),
        context,
      ),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(WelcomeScreen),
      matchesGoldenFile('goldens/welcome.png'),
    );
  });
}
