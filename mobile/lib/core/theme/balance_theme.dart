import 'package:flutter/material.dart';

abstract final class BalanceColors {
  static const ink = Color(0xFF121212);
  static const blue = Color(0xFF4F91F7);
  static const blueDark = Color(0xFF256DDB);
  static const paperBlue = Color(0xFFDCEBFA);
  static const paper = Color(0xFFFFFCF7);
  static const yellow = Color(0xFFFFD928);
  static const green = Color(0xFF19D978);
  static const orange = Color(0xFFFF7A23);
  static const muted = Color(0xFF667085);
}

abstract final class BalanceTheme {
  static ThemeData get light {
    const border = OutlineInputBorder(
      borderRadius: BorderRadius.all(Radius.circular(12)),
      borderSide: BorderSide(color: BalanceColors.ink, width: 2),
    );

    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Baloo 2',
      scaffoldBackgroundColor: BalanceColors.paperBlue,
      colorScheme: ColorScheme.fromSeed(
        seedColor: BalanceColors.blue,
        brightness: Brightness.light,
        primary: BalanceColors.blue,
        secondary: BalanceColors.yellow,
        surface: BalanceColors.paper,
      ),
      textTheme: const TextTheme(
        displaySmall: TextStyle(
          color: BalanceColors.ink,
          fontSize: 36,
          height: 1.05,
          fontWeight: FontWeight.w900,
          letterSpacing: -1.2,
        ),
        headlineSmall: TextStyle(
          color: BalanceColors.ink,
          fontSize: 26,
          fontWeight: FontWeight.w900,
          letterSpacing: -0.5,
        ),
        titleMedium: TextStyle(
          color: BalanceColors.ink,
          fontSize: 17,
          fontWeight: FontWeight.w800,
        ),
        bodyLarge: TextStyle(
          color: BalanceColors.ink,
          fontSize: 16,
          height: 1.4,
          fontWeight: FontWeight.w500,
        ),
        bodyMedium: TextStyle(
          color: BalanceColors.muted,
          fontSize: 14,
          height: 1.4,
          fontWeight: FontWeight.w500,
        ),
      ),
      inputDecorationTheme: const InputDecorationTheme(
        filled: true,
        fillColor: BalanceColors.paper,
        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 17),
        enabledBorder: border,
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.all(Radius.circular(12)),
          borderSide: BorderSide(color: BalanceColors.blueDark, width: 3),
        ),
        errorBorder: border,
        focusedErrorBorder: border,
        hintStyle: TextStyle(color: Color(0xFF98A2B3)),
      ),
    );
  }
}
