import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('detail screens share a labelled back button', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: FilledButton(
                onPressed: () => Navigator.of(context).push(
                  BalancePageRoute<void>(builder: (_) => const _DetailPage()),
                ),
                child: const Text('Mở chi tiết'),
              ),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('Mở chi tiết'));
    await tester.pumpAndSettle();

    expect(find.byTooltip('Quay lại'), findsOneWidget);
    await tester.tap(find.byTooltip('Quay lại'));
    await tester.pumpAndSettle();
    expect(find.text('Mở chi tiết'), findsOneWidget);
  });
}

class _DetailPage extends StatelessWidget {
  const _DetailPage();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(appBar: BalanceAppBar(title: 'Chi tiết'));
  }
}
