import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/mascot/domain/mascot_shape.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:balance/features/mascot/presentation/walking_mascot.dart';
import 'package:balance/features/journal/presentation/sticker_thumb.dart';
import 'package:flutter/material.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({this.now, super.key});

  /// Đồng hồ tiêm được. Golden test cần một mốc thời gian cố định, nếu không
  /// lời chào đổi theo giờ chạy test và ảnh mẫu hỏng vào buổi khác trong ngày.
  final DateTime? now;

  void _open(BuildContext context, Widget page) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final profile = state?.profile;
    final today = now ?? DateTime.now();
    final entries = state?.entriesForDate(today) ?? const [];
    final hasAppState = state != null;
    final totals = hasAppState
        ? _DayTotals.fromEntries(entries)
        : _DayTotals.demo;
    final calorieTarget = profile?.dailyCalorieTarget ?? 1800;

    return Scaffold(
      body: GraphPaperBackground(
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: () async => state?.refresh(),
            color: BalanceColors.blueDark,
            backgroundColor: BalanceColors.paper,
            child: SingleChildScrollView(
              // Nội dung ngắn hơn màn hình vẫn phải kéo được, không thì thao
              // tác tải lại chết ngay ở ngày chưa ăn gì.
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _DashboardHeader(
                    name: profile?.name ?? 'An',
                    date: hasAppState ? today : DateTime(2024, 5, 15),
                    useLegacyGreeting: !hasAppState,
                  ),
                  const SizedBox(height: 16),
                  _TodayCard(
                    totals: totals,
                    calorieTarget: calorieTarget,
                    entries: entries,
                  ),
                  const SizedBox(height: 12),
                  _MascotCard(profile: profile),
                  const SizedBox(height: 16),
                  _MealList(entries: entries, useDemo: !hasAppState),
                  const SizedBox(height: 16),
                  PressableButton(
                    label: 'Chụp món ăn',
                    icon: Icons.camera_alt_outlined,
                    onPressed: () => _open(context, const AnalyzeScreen()),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Khoảnh sân cho linh vật đi qua đi lại.
class _MascotCard extends StatelessWidget {
  const _MascotCard({required this.profile});

  final UserProfile? profile;

  @override
  Widget build(BuildContext context) {
    final shape = profile == null
        ? MascotShape.fit
        : mascotShapeFor(
            heightCm: profile!.heightCm,
            weightKg: profile!.weightKg,
          );
    return SketchCard(
      color: BalanceColors.paperBlue,
      padding: const EdgeInsets.fromLTRB(10, 8, 10, 6),
      child: WalkingMascot(shape: shape),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({
    required this.name,
    required this.date,
    required this.useLegacyGreeting,
  });

  final String name;
  final DateTime date;
  final bool useLegacyGreeting;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                useLegacyGreeting
                    ? 'Chào buổi sáng, $name!'
                    : 'Chào bạn, $name!',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              Text(
                _vietnameseDate(date),
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ],
          ),
        ),
        const Icon(Icons.notifications_none_rounded, size: 31),
      ],
    );
  }
}

class _MealList extends StatelessWidget {
  const _MealList({required this.entries, required this.useDemo});

  final List<JournalEntry> entries;
  final bool useDemo;

  @override
  Widget build(BuildContext context) {
    final calories = {
      for (final type in MealType.values)
        type: useDemo
            ? _demoCalories(type)
            : entries
                  .where((entry) => entry.mealType == type)
                  .fold<double>(0, (sum, entry) => sum + entry.calories),
    };
    return Column(
      children: [
        for (final type in [
          MealType.breakfast,
          MealType.lunch,
          MealType.dinner,
        ]) ...[
          _MealRow(
            icon: _mealIcon(type),
            name: type.label,
            calories: '${_format(calories[type] ?? 0)} kcal',
            color: _mealColor(type),
          ),
          if (type != MealType.dinner) const SizedBox(height: 10),
        ],
      ],
    );
  }
}

class _TodayCard extends StatelessWidget {
  const _TodayCard({
    required this.totals,
    required this.calorieTarget,
    this.entries = const [],
  });

  final _DayTotals totals;
  final int calorieTarget;
  final List<JournalEntry> entries;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: const Color(0xFF176EE5),
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Hôm nay',
            style: TextStyle(
              color: Colors.white,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _CalorieRing(
                  calories: totals.calories,
                  target: calorieTarget,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  children: [
                    const Icon(
                      Icons.wb_sunny_outlined,
                      color: Colors.white,
                      size: 34,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      totals.calories <= calorieTarget
                          ? 'Bạn đang đi\nđúng hướng!\nCố lên nhé!'
                          : 'Hôm nay đã vượt\nmục tiêu.\nĐiều chỉnh nhẹ nhé!',
                      textAlign: TextAlign.center,
                      style: Theme.of(
                        context,
                      ).textTheme.titleMedium?.copyWith(color: Colors.white),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (entries.isNotEmpty) ...[
            const SizedBox(height: 12),
            // Ăn gì hôm nay nhìn phát biết, khỏi phải cuộn xuống danh sách.
            Center(child: StickerStrip(entries: entries, size: 38)),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _MacroBox(
                  label: 'Đạm',
                  value: '${_format(totals.protein)}g',
                  color: const Color(0xFF218B37),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _MacroBox(
                  label: 'Carb',
                  value: '${_format(totals.carbs)}g',
                  color: BalanceColors.blueDark,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _MacroBox(
                  label: 'Béo',
                  value: '${_format(totals.fat)}g',
                  color: const Color(0xFFE94F14),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _CalorieRing extends StatelessWidget {
  const _CalorieRing({required this.calories, required this.target});

  final double calories;
  final int target;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1,
      child: Stack(
        fit: StackFit.expand,
        children: [
          CircularProgressIndicator(
            value: target <= 0 ? 0 : (calories / target).clamp(0, 1),
            strokeWidth: 12,
            backgroundColor: BalanceColors.paper,
            color: BalanceColors.yellow,
          ),
          Container(
            margin: const EdgeInsets.all(17),
            decoration: BoxDecoration(
              color: BalanceColors.paper,
              shape: BoxShape.circle,
              border: Border.all(color: BalanceColors.ink, width: 2),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  _format(calories),
                  style: const TextStyle(
                    fontSize: 34,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Text(
                  '/ ${_format(target.toDouble())} kcal',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MacroBox extends StatelessWidget {
  const _MacroBox({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 7),
      decoration: BoxDecoration(
        color: BalanceColors.paper,
        border: Border.all(color: BalanceColors.ink, width: 2),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Column(
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
          Text(
            value,
            style: TextStyle(
              color: color,
              fontSize: 25,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _MealRow extends StatelessWidget {
  const _MealRow({
    required this.icon,
    required this.name,
    required this.calories,
    required this.color,
  });

  final IconData icon;
  final String name;
  final String calories;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 11),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              name,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Text(
            calories,
            style: TextStyle(color: color, fontWeight: FontWeight.w900),
          ),
        ],
      ),
    );
  }
}

class _DayTotals {
  const _DayTotals({
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  factory _DayTotals.fromEntries(List<JournalEntry> entries) {
    return _DayTotals(
      calories: entries.fold(0, (sum, item) => sum + item.calories),
      protein: entries.fold(0, (sum, item) => sum + item.proteinGrams),
      carbs: entries.fold(0, (sum, item) => sum + item.carbsGrams),
      fat: entries.fold(0, (sum, item) => sum + item.fatGrams),
    );
  }

  static const demo = _DayTotals(
    calories: 1240,
    protein: 62,
    carbs: 148,
    fat: 38,
  );

  final double calories;
  final double protein;
  final double carbs;
  final double fat;
}

double _demoCalories(MealType type) => switch (type) {
  MealType.breakfast => 420,
  MealType.lunch => 610,
  MealType.dinner => 210,
  MealType.snack => 0,
};

IconData _mealIcon(MealType type) => switch (type) {
  MealType.breakfast => Icons.wb_sunny_outlined,
  MealType.lunch => Icons.wb_sunny_rounded,
  MealType.dinner => Icons.nightlight_round,
  MealType.snack => Icons.cookie_outlined,
};

Color _mealColor(MealType type) => switch (type) {
  MealType.breakfast => const Color(0xFF238737),
  MealType.lunch => BalanceColors.blueDark,
  MealType.dinner => const Color(0xFFE94F14),
  MealType.snack => BalanceColors.orange,
};

String _format(double value) {
  if (value != value.roundToDouble()) return value.toStringAsFixed(1);
  final raw = value.round().toString();
  return raw.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => '.');
}

String _vietnameseDate(DateTime date) {
  const weekdays = [
    'Thứ Hai',
    'Thứ Ba',
    'Thứ Tư',
    'Thứ Năm',
    'Thứ Sáu',
    'Thứ Bảy',
    'Chủ Nhật',
  ];
  return '${weekdays[date.weekday - 1]}, ${date.day} tháng ${date.month}, ${date.year}';
}
