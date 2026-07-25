import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('uses the approved rounded font throughout the app', () {
    final theme = BalanceTheme.light;

    expect(theme.textTheme.bodyMedium?.fontFamily, 'Baloo 2');
    expect(theme.textTheme.displaySmall?.fontFamily, 'Baloo 2');
  });
}
