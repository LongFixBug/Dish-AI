import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('uses the approved rounded font throughout the app', () {
    final theme = BalanceTheme.light;

    expect(theme.textTheme.bodyMedium?.fontFamily, 'Baloo 2');
    expect(theme.textTheme.displaySmall?.fontFamily, 'Baloo 2');
  });

  test('uses the approved neo-brutalist notebook palette', () {
    expect(BalanceColors.ink, const Color(0xFF111111));
    expect(BalanceColors.paper, const Color(0xFFF8F8F8));
    expect(BalanceColors.paperBlue, const Color(0xFFDCEAF7));
    expect(BalanceColors.grid, const Color(0xFF94AEC5));
    expect(BalanceColors.blue, const Color(0xFF5294F5));
    expect(BalanceColors.green, const Color(0xFF43C46B));
    expect(BalanceColors.yellow, const Color(0xFFFFD83D));
  });

  test('exposes a matching dark palette for system dark mode', () {
    final darkTheme = BalanceTheme.dark;
    final palette = darkTheme.extension<BalancePalette>();

    expect(darkTheme.colorScheme.brightness, Brightness.dark);
    expect(darkTheme.scaffoldBackgroundColor, palette?.background);
    expect(palette?.background, const Color(0xFF101823));
    expect(palette?.surface, const Color(0xFF17212E));
    expect(palette?.ink, const Color(0xFFF7F8FA));
    expect(palette?.grid, const Color(0xFF3A4B60));
    expect(palette?.primary, const Color(0xFF72A9FF));
  });

  test('uses compact corners and hard black notebook shadows', () {
    expect(BalanceRadii.card, lessThanOrEqualTo(12));
    expect(BalanceRadii.sheet, lessThanOrEqualTo(12));
    expect(BalanceShadows.card.blurRadius, 0);
    expect(BalanceShadows.card.offset, const Offset(4, 5));
    expect(BalanceShadows.card.color, BalanceColors.ink);
  });

  test('builds a theme with custom font, accent and button colors', () {
    final theme = BalanceTheme.lightWith(
      fontFamily: 'sans-serif',
      primary: BalanceColors.coral,
      button: BalanceColors.green,
    );
    final palette = theme.extension<BalancePalette>();

    expect(theme.textTheme.bodyMedium?.fontFamily, 'sans-serif');
    expect(palette?.primary, BalanceColors.coral);
    expect(palette?.button, BalanceColors.green);
    expect(theme.filledButtonTheme.style?.backgroundColor?.resolve({}),
        BalanceColors.green);
  });

  test('theme exposes accessible touch targets and modern field shapes', () {
    final theme = BalanceTheme.light;
    final inputBorder = theme.inputDecorationTheme.enabledBorder;

    expect(theme.colorScheme.primary, BalanceColors.blue);
    expect(theme.filledButtonTheme.style?.minimumSize?.resolve({})?.height, 56);
    expect(inputBorder, isA<OutlineInputBorder>());
    expect(
      (inputBorder! as OutlineInputBorder).borderRadius.topLeft.x,
      BalanceRadii.control,
    );
  });
}
