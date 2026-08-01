import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_notice.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('brand notice keeps a visible ink-card action', (tester) async {
    var retried = false;

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: Scaffold(
          body: BalanceNotice(
            icon: Icons.info_outline_rounded,
            title: 'Cần lưu ý',
            message: 'Đây là thông tin quan trọng.',
            actionLabel: 'Xem lại',
            onAction: () => retried = true,
          ),
        ),
      ),
    );

    expect(find.text('Cần lưu ý'), findsOneWidget);
    expect(find.text('Xem lại'), findsOneWidget);
    await tester.tap(find.text('Xem lại'));
    expect(retried, isTrue);
  });

  testWidgets('app-bar icon controls use the raised Balance control', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: Scaffold(
          appBar: BalanceAppBar(
            title: 'Mẫu',
            showBackButton: false,
            actions: [
              BalanceIconButton(
                tooltip: 'Thông tin',
                icon: Icons.info_outline_rounded,
                onPressed: () {},
              ),
            ],
          ),
        ),
      ),
    );

    expect(
      find.byKey(const ValueKey('balance-icon-button-Thông tin')),
      findsOneWidget,
    );
    expect(find.byTooltip('Thông tin'), findsOneWidget);
  });

  testWidgets('notebook cards use the shared soft surface treatment', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: const Scaffold(body: SketchCard(child: Text('Năng lượng'))),
      ),
    );

    final decorated = tester.widget<Container>(
      find.descendant(
        of: find.byType(SketchCard),
        matching: find.byType(Container),
      ),
    );
    final decoration = decorated.decoration! as BoxDecoration;

    expect(decoration.borderRadius, BorderRadius.circular(BalanceRadii.card));
    expect(decoration.boxShadow, contains(BalanceShadows.card));
    expect((decoration.border! as Border).top.color, BalanceColors.ink);
    expect((decoration.border! as Border).top.width, BalanceStrokes.strong);
  });

  testWidgets('sketch cards follow the active theme surface colors', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.dark,
        home: const Scaffold(body: SketchCard(child: Text('Năng lượng'))),
      ),
    );

    final context = tester.element(find.byType(SketchCard));
    final palette = BalanceTheme.paletteOf(context);
    final decorated = tester.widget<Container>(
      find.descendant(
        of: find.byType(SketchCard),
        matching: find.byType(Container),
      ),
    );
    final decoration = decorated.decoration! as BoxDecoration;

    expect(decoration.color, palette.surface);
    expect((decoration.border! as Border).top.color, palette.ink);
  });
}
