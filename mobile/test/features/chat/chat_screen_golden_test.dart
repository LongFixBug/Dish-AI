@Tags(['golden'])
library;

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/chat/presentation/chat_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/load_test_fonts.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await loadBalanceTestFonts();
  });

  testWidgets('màn chat trống giữ phong cách giấy kẻ ô', (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(theme: BalanceTheme.light, home: const ChatScreen()),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(ChatScreen),
      matchesGoldenFile('goldens/chat_empty.png'),
    );
  });
}
