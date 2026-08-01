import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/chat/presentation/chat_screen.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/nutrition/presentation/nutrition_goal_screen.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({this.now, this.animationSeed = 0, super.key});

  /// Đồng hồ tiêm được để golden test và lời chào không phụ thuộc giờ chạy.
  final DateTime? now;
  final int animationSeed;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with SingleTickerProviderStateMixin {
  static const _duration = Duration(milliseconds: 1550);
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _duration,
  );
  bool _didStartInitialAnimation = false;

  @override
  void initState() {
    super.initState();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_didStartInitialAnimation) return;
    _didStartInitialAnimation = true;
    _playEntryAnimation();
  }

  @override
  void didUpdateWidget(covariant DashboardScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.animationSeed != widget.animationSeed) {
      _playEntryAnimation();
    }
  }

  void _playEntryAnimation() {
    final disableAnimations =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (disableAnimations) {
      _controller.value = 1;
      return;
    }
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _open(BuildContext context, Widget page) {
    Navigator.of(context).push(BalancePageRoute<void>(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final profile = state?.profile;
    final today = widget.now ?? DateTime.now();
    final entries = state?.entriesForDate(today) ?? const <JournalEntry>[];
    final totals = state == null
        ? _DayTotals.demo
        : _DayTotals.fromEntries(entries);
    final calorieTarget = profile?.dailyCalorieTarget ?? 1800;

    return BalanceScreenMotion(
      seed: widget.animationSeed,
      child: Scaffold(
        body: GraphPaperBackground(
          child: SafeArea(
            child: RefreshIndicator(
              onRefresh: () async => state?.refresh(),
              color: BalanceColors.blueDark,
              backgroundColor: BalanceColors.paper,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _EntryReveal(
                      animation: CurvedAnimation(
                        parent: _controller,
                        curve: const Interval(
                          0.04,
                          0.30,
                          curve: Curves.easeOut,
                        ),
                      ),
                      child: _DashboardHeader(
                        name: profile?.name ?? 'An',
                        date: state == null ? DateTime(2024, 5, 15, 9) : today,
                        onChat: () => _open(context, const ChatScreen()),
                      ),
                    ),
                    const SizedBox(height: 14),
                    _EntryReveal(
                      animation: CurvedAnimation(
                        parent: _controller,
                        curve: const Interval(
                          0.18,
                          0.70,
                          curve: Curves.easeOut,
                        ),
                      ),
                      offsetY: 16,
                      child: Semantics(
                        button: profile != null,
                        label: 'Xem nhu cầu dinh dưỡng',
                        child: GestureDetector(
                          onTap: profile == null
                              ? null
                              : () =>
                                    _open(context, const NutritionGoalScreen()),
                          child: _TodayOverview(
                            totals: totals,
                            calorieTarget: calorieTarget,
                            animation: CurvedAnimation(
                              parent: _controller,
                              curve: const Interval(
                                0.24,
                                0.88,
                                curve: Curves.easeOutCubic,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 12),
                    _EntryReveal(
                      animation: CurvedAnimation(
                        parent: _controller,
                        curve: const Interval(
                          0.42,
                          0.86,
                          curve: Curves.easeOut,
                        ),
                      ),
                      offsetY: 14,
                      child: _RecommendationCard(
                        onTap: () => _open(context, const SuggestionsScreen()),
                      ),
                    ),
                    const SizedBox(height: 12),
                    _EntryReveal(
                      animation: CurvedAnimation(
                        parent: _controller,
                        curve: const Interval(
                          0.56,
                          1.00,
                          curve: Curves.easeOut,
                        ),
                      ),
                      offsetY: 14,
                      child: _HabitCard(
                        onScan: () => _open(context, const AnalyzeScreen()),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader({
    required this.name,
    required this.date,
    required this.onChat,
  });

  final String name;
  final DateTime date;
  final VoidCallback onChat;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${_greeting(date.hour)}, $name!',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 1),
              Text(
                _vietnameseDate(date),
                style: const TextStyle(
                  color: BalanceColors.muted,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        BalanceIconButton(
          tooltip: 'Hỏi Balance',
          icon: Icons.chat_bubble_outline_rounded,
          onPressed: onChat,
        ),
      ],
    );
  }
}

class _TodayOverview extends StatelessWidget {
  const _TodayOverview({
    required this.totals,
    required this.calorieTarget,
    required this.animation,
  });

  final _DayTotals totals;
  final int calorieTarget;
  final Animation<double> animation;

  @override
  Widget build(BuildContext context) {
    final remaining = (calorieTarget - totals.calories).clamp(0, calorieTarget);
    return SketchCard(
      key: const ValueKey('dashboard-today-overview'),
      radius: BalanceRadii.card,
      color: const Color(0xFFF8FBFF),
      padding: const EdgeInsets.fromLTRB(16, 15, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Cân bằng hôm nay',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 5,
                ),
                decoration: BoxDecoration(
                  color: BalanceColors.mint.withValues(alpha: 0.62),
                  borderRadius: BorderRadius.circular(BalanceRadii.pill),
                ),
                child: Text(
                  '${_format(remaining.toDouble())} kcal còn lại',
                  style: const TextStyle(
                    color: BalanceColors.ink,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'ĐÃ NẠP',
                      style: TextStyle(
                        color: BalanceColors.muted,
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.8,
                      ),
                    ),
                    Text(
                      _format(totals.calories),
                      style: const TextStyle(
                        color: BalanceColors.blueDark,
                        fontSize: 34,
                        height: 1.05,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      '/ ${_format(calorieTarget.toDouble())} kcal',
                      style: const TextStyle(
                        color: BalanceColors.muted,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              _HeroVisual(
                calories: totals.calories,
                target: calorieTarget,
                animation: animation,
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: _MacroBox(
                  label: 'Đạm',
                  value: '${_format(totals.protein)} g',
                  color: const Color(0xFF205E2C),
                  background: const Color(0xFF82BA43),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _MacroBox(
                  label: 'Carb',
                  value: '${_format(totals.carbs)} g',
                  color: const Color(0xFF0B4586),
                  background: const Color(0xFF2E86D8),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _MacroBox(
                  label: 'Béo',
                  value: '${_format(totals.fat)} g',
                  color: const Color(0xFFC54112),
                  background: const Color(0xFFFF8A0B),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _HeroVisual extends StatelessWidget {
  const _HeroVisual({
    required this.calories,
    required this.target,
    required this.animation,
  });

  final double calories;
  final int target;
  final Animation<double> animation;

  @override
  Widget build(BuildContext context) {
    final progress = target <= 0 ? 0.0 : (calories / target).clamp(0.0, 1.0);
    return SizedBox(
      width: 104,
      height: 104,
      child: AnimatedBuilder(
        animation: animation,
        builder: (context, _) {
          final eased = Curves.easeOutCubic.transform(animation.value);
          final currentProgress = progress * eased;
          return Stack(
            fit: StackFit.expand,
            children: [
              Container(
                margin: const EdgeInsets.all(6),
                decoration: const BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                ),
              ),
              CircularProgressIndicator(
                value: currentProgress,
                strokeWidth: 8,
                strokeCap: StrokeCap.round,
                backgroundColor: BalanceColors.blue.withValues(alpha: 0.12),
                color: BalanceColors.blue,
              ),
              Center(
                child: Text(
                  '${(currentProgress * 100).round()}%',
                  style: const TextStyle(
                    color: BalanceColors.blueDark,
                    fontSize: 21,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _EntryReveal extends StatelessWidget {
  const _EntryReveal({
    required this.animation,
    required this.child,
    this.offsetY = 10,
  });

  final Animation<double> animation;
  final Widget child;
  final double offsetY;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      child: child,
      builder: (context, child) {
        final t = Curves.easeOutCubic.transform(
          animation.value.clamp(0.0, 1.0),
        );
        return Opacity(
          opacity: t,
          child: Transform.translate(
            offset: Offset(0, (1 - t) * offsetY),
            child: child,
          ),
        );
      },
    );
  }
}

class _MacroBox extends StatelessWidget {
  const _MacroBox({
    required this.label,
    required this.value,
    required this.color,
    required this.background,
  });

  final String label;
  final String value;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 10),
      decoration: BoxDecoration(
        color: background,
        border: Border.all(
          color: BalanceColors.ink,
          width: BalanceStrokes.regular,
        ),
        borderRadius: BorderRadius.circular(BalanceRadii.small),
        boxShadow: const [BalanceShadows.card],
      ),
      child: Column(
        children: [
          Text(
            label,
            style: TextStyle(color: color, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 2),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              value,
              style: TextStyle(
                color: BalanceColors.ink,
                fontSize: 23,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _RecommendationCard extends StatelessWidget {
  const _RecommendationCard({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Mở gợi ý món ăn',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(BalanceRadii.card),
        child: SketchCard(
          key: const ValueKey('dashboard-recommendation'),
          radius: BalanceRadii.card,
          color: const Color(0xFFFFFAF2),
          padding: const EdgeInsets.fromLTRB(14, 13, 12, 13),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Gợi ý cho bạn',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(16),
                    child: const SizedBox(
                      width: 96,
                      height: 82,
                      child: FoodPhoto(meal: FoodPhotoMeal.caKho),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Cá kho + rau luộc',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        SizedBox(height: 6),
                        Wrap(
                          spacing: 6,
                          runSpacing: 4,
                          children: [
                            _SuggestionBadge(
                              label: '420 kcal',
                              color: BalanceColors.paperBlue,
                            ),
                            _SuggestionBadge(
                              label: 'Phù hợp',
                              color: Color(0xFFDDF8E6),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 5),
                  const Icon(Icons.chevron_right_rounded, size: 28),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SuggestionBadge extends StatelessWidget {
  const _SuggestionBadge({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color,
        border: Border.all(
          color: BalanceColors.ink.withValues(alpha: 0.25),
          width: 1,
        ),
        borderRadius: BorderRadius.circular(BalanceRadii.pill),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800),
      ),
    );
  }
}

class _HabitCard extends StatefulWidget {
  const _HabitCard({required this.onScan});

  final VoidCallback onScan;

  @override
  State<_HabitCard> createState() => _HabitCardState();
}

class _HabitCardState extends State<_HabitCard> {
  final _completed = <bool>[true, false, true];

  @override
  Widget build(BuildContext context) {
    final completedCount = _completed.where((value) => value).length;
    return SketchCard(
      key: const ValueKey('dashboard-habits'),
      radius: BalanceRadii.card,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Thói quen',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
                ),
              ),
              Text(
                '$completedCount/3 hoàn thành',
                style: const TextStyle(
                  color: BalanceColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          const SizedBox(height: 5),
          _HabitRow(
            icon: Icons.water_drop_outlined,
            label: 'Uống đủ nước',
            color: BalanceColors.blue,
            progress: 0.62,
            completed: _completed[0],
            onTap: () => _toggle(0),
          ),
          _HabitRow(
            icon: Icons.directions_walk_rounded,
            label: 'Đi bộ 30 phút',
            color: BalanceColors.blueDark,
            progress: 0.4,
            completed: _completed[1],
            onTap: () => _toggle(1),
          ),
          _HabitRow(
            icon: Icons.eco_outlined,
            label: 'Ăn rau xanh',
            color: const Color(0xFF218B37),
            progress: 0.72,
            completed: _completed[2],
            onTap: () => _toggle(2),
          ),
          const SizedBox(height: 8),
          PressableButton(
            label: 'Quét món ăn',
            icon: Icons.camera_alt_outlined,
            onPressed: widget.onScan,
          ),
        ],
      ),
    );
  }

  void _toggle(int index) {
    setState(() => _completed[index] = !_completed[index]);
  }
}

class _HabitRow extends StatelessWidget {
  const _HabitRow({
    required this.icon,
    required this.label,
    required this.color,
    required this.progress,
    required this.completed,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color color;
  final double progress;
  final bool completed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 42,
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.16),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: color, size: 19),
          ),
          const SizedBox(width: 9),
          Expanded(
            flex: 4,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
          Expanded(
            flex: 3,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: LinearProgressIndicator(
                value: progress,
                minHeight: 5,
                backgroundColor: const Color(0xFFE4E4E4),
                color: color,
              ),
            ),
          ),
          const SizedBox(width: 10),
          Semantics(
            button: true,
            checked: completed,
            label: '$label ${completed ? 'đã hoàn thành' : 'chưa hoàn thành'}',
            child: GestureDetector(
              onTap: onTap,
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 160),
                width: 25,
                height: 25,
                decoration: BoxDecoration(
                  color: completed
                      ? const Color(0xFF218B37)
                      : BalanceColors.paper,
                  shape: BoxShape.circle,
                  border: Border.all(color: BalanceColors.ink, width: 1.5),
                ),
                child: completed
                    ? const Icon(
                        Icons.check_rounded,
                        color: Colors.white,
                        size: 17,
                      )
                    : null,
              ),
            ),
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
    protein: 68,
    carbs: 142,
    fat: 38,
  );

  final double calories;
  final double protein;
  final double carbs;
  final double fat;
}

String _greeting(int hour) => switch (hour) {
  < 12 => 'Chào buổi sáng',
  < 18 => 'Chào buổi chiều',
  _ => 'Chào buổi tối',
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
