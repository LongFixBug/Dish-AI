import 'package:flutter/material.dart';

abstract final class BalanceColors {
  // Mực đen rõ như poster trong ảnh mẫu; màu nhấn được phép rực để card
  // đọc được ngay trên nền giấy ô ly xanh.
  static const ink = Color(0xFF111111);
  static const blue = Color(0xFF5294F5);
  static const blueDark = Color(0xFF2479DC);
  static const lightBlue = Color(0xFF9CCBFA);
  static const cyan = Color(0xFF55C9E8);
  static const paperBlue = Color(0xFFDCEAF7);
  static const paper = Color(0xFFF8F8F8);

  // Nền đặt sticker. Sticker có viền TRẮNG, đặt lên `paper` (#FFFCF7 — kem
  // gần trắng) là viền tàng hình; tông hồng kem đủ đậm để đường viền hiện ra
  // mà vẫn nằm trong bảng màu ấm của app.
  static const stickerMat = Color(0xFFFFEDE6);
  static const yellow = Color(0xFFFFD83D);
  static const green = Color(0xFF43C46B);
  static const darkGreen = Color(0xFF2F7D39);
  static const mint = Color(0xFFCFF1D9);
  static const coral = Color(0xFFEC6E91);
  static const orange = Color(0xFFFF9E3D);
  static const lavender = Color(0xFFA66BD1);
  static const muted = Color(0xFF7A818D);
  static const bodyText = Color(0xFF505866);
  static const grid = Color(0xFF94AEC5);
  static const dangerPaper = Color(0xFFFFE4DE);
  static const danger = Color(0xFFE95143);
}

abstract final class BalanceRadii {
  static const small = 10.0;
  static const control = 10.0;
  static const card = 12.0;
  static const sheet = 12.0;
  static const pill = 999.0;
}

abstract final class BalanceStrokes {
  static const strong = 2.5;
  static const regular = 2.0;
}

abstract final class BalanceShadows {
  static const card = BoxShadow(
    color: BalanceColors.ink,
    offset: Offset(4, 5),
    blurRadius: 0,
  );
  static const button = BoxShadow(
    color: BalanceColors.ink,
    offset: Offset(4, 5),
    blurRadius: 0,
  );
  static const floating = BoxShadow(
    color: BalanceColors.ink,
    offset: Offset(4, 5),
    blurRadius: 0,
  );
}

@immutable
class BalancePalette extends ThemeExtension<BalancePalette> {
  const BalancePalette({
    required this.background,
    required this.grid,
    required this.surface,
    required this.surfaceSoft,
    required this.ink,
    required this.muted,
    required this.bodyText,
    required this.primary,
    required this.primaryDark,
    required this.secondary,
    required this.success,
    required this.warning,
    required this.danger,
    required this.warningSurface,
    required this.dangerSurface,
    required this.shadow,
  });

  const BalancePalette.light()
    : background = BalanceColors.paperBlue,
      grid = BalanceColors.grid,
      surface = BalanceColors.paper,
      surfaceSoft = BalanceColors.paperBlue,
      ink = BalanceColors.ink,
      muted = BalanceColors.muted,
      bodyText = BalanceColors.bodyText,
      primary = BalanceColors.blue,
      primaryDark = BalanceColors.blueDark,
      secondary = BalanceColors.yellow,
      success = BalanceColors.green,
      warning = BalanceColors.orange,
      danger = BalanceColors.danger,
      warningSurface = const Color(0xFFFFF1C7),
      dangerSurface = BalanceColors.dangerPaper,
      shadow = BalanceColors.ink;

  const BalancePalette.dark()
    : background = const Color(0xFF101823),
      grid = const Color(0xFF3A4B60),
      surface = const Color(0xFF17212E),
      surfaceSoft = const Color(0xFF1E2A38),
      ink = const Color(0xFFF7F8FA),
      muted = const Color(0xFF9BA8B8),
      bodyText = const Color(0xFFD7DFEA),
      primary = const Color(0xFF72A9FF),
      primaryDark = const Color(0xFF4F8AF0),
      secondary = const Color(0xFFFFD966),
      success = const Color(0xFF59D685),
      warning = const Color(0xFFFFB74D),
      danger = const Color(0xFFFF7867),
      warningSurface = const Color(0xFF2C2616),
      dangerSurface = const Color(0xFF321815),
      shadow = const Color(0xFF05070B);

  final Color background;
  final Color grid;
  final Color surface;
  final Color surfaceSoft;
  final Color ink;
  final Color muted;
  final Color bodyText;
  final Color primary;
  final Color primaryDark;
  final Color secondary;
  final Color success;
  final Color warning;
  final Color danger;
  final Color warningSurface;
  final Color dangerSurface;
  final Color shadow;

  @override
  BalancePalette copyWith({
    Color? background,
    Color? grid,
    Color? surface,
    Color? surfaceSoft,
    Color? ink,
    Color? muted,
    Color? bodyText,
    Color? primary,
    Color? primaryDark,
    Color? secondary,
    Color? success,
    Color? warning,
    Color? danger,
    Color? warningSurface,
    Color? dangerSurface,
    Color? shadow,
  }) {
    return BalancePalette(
      background: background ?? this.background,
      grid: grid ?? this.grid,
      surface: surface ?? this.surface,
      surfaceSoft: surfaceSoft ?? this.surfaceSoft,
      ink: ink ?? this.ink,
      muted: muted ?? this.muted,
      bodyText: bodyText ?? this.bodyText,
      primary: primary ?? this.primary,
      primaryDark: primaryDark ?? this.primaryDark,
      secondary: secondary ?? this.secondary,
      success: success ?? this.success,
      warning: warning ?? this.warning,
      danger: danger ?? this.danger,
      warningSurface: warningSurface ?? this.warningSurface,
      dangerSurface: dangerSurface ?? this.dangerSurface,
      shadow: shadow ?? this.shadow,
    );
  }

  @override
  BalancePalette lerp(ThemeExtension<BalancePalette>? other, double t) {
    if (other is! BalancePalette) return this;
    return BalancePalette(
      background: Color.lerp(background, other.background, t)!,
      grid: Color.lerp(grid, other.grid, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceSoft: Color.lerp(surfaceSoft, other.surfaceSoft, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      muted: Color.lerp(muted, other.muted, t)!,
      bodyText: Color.lerp(bodyText, other.bodyText, t)!,
      primary: Color.lerp(primary, other.primary, t)!,
      primaryDark: Color.lerp(primaryDark, other.primaryDark, t)!,
      secondary: Color.lerp(secondary, other.secondary, t)!,
      success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      warningSurface: Color.lerp(warningSurface, other.warningSurface, t)!,
      dangerSurface: Color.lerp(dangerSurface, other.dangerSurface, t)!,
      shadow: Color.lerp(shadow, other.shadow, t)!,
    );
  }
}

abstract final class BalanceTheme {
  static ThemeData get light => _build(
    palette: const BalancePalette.light(),
    brightness: Brightness.light,
  );

  static ThemeData get dark =>
      _build(palette: const BalancePalette.dark(), brightness: Brightness.dark);

  static BalancePalette paletteOf(BuildContext context) {
    return Theme.of(context).extension<BalancePalette>() ??
        const BalancePalette.light();
  }

  static ThemeData _build({
    required BalancePalette palette,
    required Brightness brightness,
  }) {
    final border = OutlineInputBorder(
      borderRadius: const BorderRadius.all(
        Radius.circular(BalanceRadii.control),
      ),
      borderSide: BorderSide(color: palette.ink, width: BalanceStrokes.strong),
    );
    final focusBorder = OutlineInputBorder(
      borderRadius: const BorderRadius.all(
        Radius.circular(BalanceRadii.control),
      ),
      borderSide: BorderSide(color: palette.primaryDark, width: 3),
    );
    final scheme =
        ColorScheme.fromSeed(
          seedColor: palette.primary,
          brightness: brightness,
          primary: palette.primary,
          secondary: palette.secondary,
          surface: palette.surface,
          error: palette.danger,
        ).copyWith(
          onPrimary: brightness == Brightness.dark
              ? Colors.white
              : Colors.white,
          onSecondary: palette.ink,
          onSurface: palette.ink,
          surfaceContainerHighest: palette.surfaceSoft,
          surfaceContainerLow: palette.surfaceSoft,
          outline: palette.ink,
          errorContainer: palette.dangerSurface,
          onErrorContainer: palette.ink,
          inverseSurface: brightness == Brightness.dark
              ? const Color(0xFFF7F8FA)
              : const Color(0xFF111111),
          inversePrimary: palette.primary,
        );

    return ThemeData(
      useMaterial3: true,
      fontFamily: 'Baloo 2',
      brightness: brightness,
      scaffoldBackgroundColor: palette.background,
      cardColor: palette.surface,
      colorScheme: scheme,
      extensions: <ThemeExtension<dynamic>>[palette],
      textTheme: TextTheme(
        displaySmall: TextStyle(
          color: palette.ink,
          fontSize: 36,
          height: 1.05,
          fontWeight: FontWeight.w900,
          letterSpacing: 0,
        ),
        headlineSmall: TextStyle(
          color: palette.ink,
          fontSize: 26,
          fontWeight: FontWeight.w900,
          letterSpacing: 0,
        ),
        titleLarge: TextStyle(
          color: palette.ink,
          fontSize: 22,
          height: 1.15,
          fontWeight: FontWeight.w900,
          letterSpacing: 0,
        ),
        titleMedium: TextStyle(
          color: palette.ink,
          fontSize: 17,
          fontWeight: FontWeight.w800,
          letterSpacing: 0,
        ),
        bodyLarge: TextStyle(
          color: palette.ink,
          fontSize: 16,
          height: 1.4,
          fontWeight: FontWeight.w500,
          letterSpacing: 0,
        ),
        bodyMedium: TextStyle(
          color: palette.bodyText,
          fontSize: 14,
          height: 1.4,
          fontWeight: FontWeight.w500,
          letterSpacing: 0,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: palette.surface,
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 17,
        ),
        enabledBorder: border,
        focusedBorder: focusBorder,
        errorBorder: border,
        focusedErrorBorder: border,
        hintStyle: TextStyle(color: palette.muted),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: palette.primary,
          foregroundColor: Colors.white,
          minimumSize: const Size.fromHeight(56),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(BalanceRadii.control),
            side: BorderSide(color: palette.ink, width: BalanceStrokes.regular),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: palette.ink,
          minimumSize: const Size.fromHeight(56),
          side: BorderSide(color: palette.ink, width: BalanceStrokes.regular),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(BalanceRadii.control),
          ),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: palette.primaryDark,
          textStyle: const TextStyle(fontWeight: FontWeight.w900),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: palette.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(BalanceRadii.card),
          side: BorderSide(color: palette.ink, width: BalanceStrokes.strong),
        ),
      ),
      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: palette.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(BalanceRadii.sheet),
          side: BorderSide(color: palette.ink, width: BalanceStrokes.strong),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: palette.surface,
        contentTextStyle: TextStyle(
          color: palette.ink,
          fontWeight: FontWeight.w800,
        ),
        actionTextColor: palette.primaryDark,
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(BalanceRadii.control),
          side: BorderSide(color: palette.ink, width: BalanceStrokes.regular),
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: palette.ink,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: palette.ink,
          fontFamily: 'Baloo 2',
          fontSize: 21,
          fontWeight: FontWeight.w900,
        ),
      ),
      dividerTheme: DividerThemeData(
        color: palette.ink.withValues(
          alpha: brightness == Brightness.dark ? 0.18 : 0.14,
        ),
        thickness: 1,
      ),
    );
  }
}
