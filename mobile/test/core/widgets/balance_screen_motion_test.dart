import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('content stays visible when tickers are disabled', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: TickerMode(
          enabled: false,
          child: BalanceScreenMotion(
            child: Scaffold(
              body: BalanceReveal(child: Text('Nội dung Balance')),
            ),
          ),
        ),
      ),
    );

    final opacity = tester.widget<Opacity>(
      find.ancestor(
        of: find.text('Nội dung Balance'),
        matching: find.byType(Opacity),
      ),
    );
    expect(opacity.opacity, 1);
  });
}
