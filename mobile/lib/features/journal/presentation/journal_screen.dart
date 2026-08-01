import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/domain/month_grid.dart';
import 'package:balance/features/journal/domain/month_stats.dart';
import 'package:balance/features/journal/presentation/month_summary.dart';
import 'package:balance/features/journal/presentation/sticker_calendar.dart';
import 'package:balance/features/journal/presentation/sticker_thumb.dart';
import 'package:flutter/material.dart';

class JournalScreen extends StatefulWidget {
  const JournalScreen({
    this.now,
    this.animateMonthPile = true,
    this.animationSeed = 0,
    super.key,
  });

  /// Đồng hồ tiêm được cho test; bỏ trống thì lấy giờ máy.
  final DateTime? now;

  /// Tắt mô phỏng rơi trong golden test để ảnh chụp luôn xác định.
  final bool animateMonthPile;
  final int animationSeed;

  @override
  State<JournalScreen> createState() => _JournalScreenState();
}

class _JournalScreenState extends State<JournalScreen> {
  DateTime? _selectedDay;
  DateTime? _visibleMonth;

  /// Đổi sau mỗi lần tải lại để đống sticker được dựng mới và rơi lại từ đầu.
  int _refreshToken = 0;

  DateTime get _today => widget.now ?? DateTime.now();

  Future<void> _refresh() async {
    await AppScope.maybeOf(context)?.refresh();
    if (mounted) setState(() => _refreshToken += 1);
  }

  Future<void> _removeWithUndo(AppState state, JournalEntry entry) async {
    final removed = await state.removeJournalEntry(
      entry.id,
      deleteSticker: false,
    );
    if (!mounted || removed == null) return;
    final snackBar = ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        backgroundColor: BalanceColors.paper,
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 18),
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: BalanceColors.ink, width: 2),
          borderRadius: BorderRadius.circular(12),
        ),
        content: Row(
          children: [
            Container(
              width: 30,
              height: 30,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: const Color(0xFFFFE4DE),
                border: Border.all(color: BalanceColors.ink, width: 1.4),
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.delete_outline_rounded, size: 18),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Đã xoá ${entry.dishName} khỏi nhật ký',
                style: const TextStyle(
                  color: BalanceColors.ink,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
        ),
        action: SnackBarAction(
          label: 'Hoàn tác',
          textColor: BalanceColors.blueDark,
          onPressed: () => state.restoreJournalEntry(removed),
        ),
      ),
    );
    final reason = await snackBar.closed;
    if (reason != SnackBarClosedReason.action) {
      await state.deleteJournalEntrySticker(removed);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final today = _today;
    final selected = _selectedDay ?? today;
    final month = _visibleMonth ?? DateTime(today.year, today.month);
    final all = state?.journalEntries ?? const <JournalEntry>[];
    final monthEntries = entriesInMonth(all, month);
    final entries =
        entriesByDay(all)[DayKey.from(selected)] ?? const <JournalEntry>[];
    final calorieTarget = state?.profile?.dailyCalorieTarget ?? 2000;
    return BalanceScreenMotion(
      seed: widget.animationSeed,
      child: Scaffold(
        appBar: const BalanceAppBar(title: 'Nhật ký ăn uống'),
        body: GraphPaperBackground(
          child: SafeArea(
            top: false,
            child: RefreshIndicator(
              onRefresh: _refresh,
              color: BalanceColors.blueDark,
              backgroundColor: BalanceColors.paper,
              child: ListView(
                // Luôn cuộn được: danh sách ngắn hơn màn hình vẫn phải kéo
                // xuống tải lại được, không thì thao tác chết ở ngày trống.
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
                children: [
                  // Hai khối này là bản sắc riêng của Journal: giữ nguyên pile
                  // sticker và lịch tháng, chỉ sắp lại hierarchy xung quanh.
                  BalanceReveal(
                    index: 0,
                    child: MonthStickerPile(
                      key: ValueKey('pile-$_refreshToken-${month.month}'),
                      month: month,
                      entries: monthEntries,
                      height: 180,
                      animate: widget.animateMonthPile,
                    ),
                  ),
                  if (monthEntries.any(
                    (entry) => (entry.stickerPath ?? '').isNotEmpty,
                  ))
                    const SizedBox(height: 16),
                  BalanceReveal(
                    index: 1,
                    child: StickerCalendar(
                      month: month,
                      entries: all,
                      today: today,
                      onDayTap: (day) => setState(() {
                        _selectedDay = day;
                        _visibleMonth = DateTime(day.year, day.month);
                      }),
                      onMonthChanged: (next) =>
                          setState(() => _visibleMonth = next),
                    ),
                  ),
                  const SizedBox(height: 16),
                  BalanceReveal(
                    index: 2,
                    child: _JournalDayOverview(
                      date: selected,
                      entries: entries,
                      calorieTarget: calorieTarget,
                    ),
                  ),
                  const SizedBox(height: 16),
                  BalanceReveal(
                    index: 3,
                    child: _MealSectionHeader(
                      onAdd: () => Navigator.of(context).push(
                        BalancePageRoute<void>(
                          builder: (_) => const AnalyzeScreen(),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  if (entries.isEmpty)
                    const BalanceReveal(index: 4, child: _EmptyDay()),
                  for (var i = 0; i < entries.length; i++)
                    BalanceReveal(
                      index: 4 + i.clamp(0, 3),
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Dismissible(
                          key: ValueKey(entries[i].id),
                          direction: DismissDirection.endToStart,
                          background: const SizedBox.expand(),
                          secondaryBackground: _JournalDeleteBackground(
                            key: ValueKey('journal-delete-${entries[i].id}'),
                            dishName: entries[i].dishName,
                          ),
                          onDismissed: (_) {
                            if (state != null) {
                              _removeWithUndo(state, entries[i]);
                            }
                          },
                          child: _JournalEntryCard(entry: entries[i]),
                        ),
                      ),
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

/// Ngày được chọn chưa ghi món nào.
class _EmptyDay extends StatelessWidget {
  const _EmptyDay();

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: const Color(0xFFFFF4D6),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      child: Row(
        children: [
          const Icon(Icons.no_meals_rounded, size: 26),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Chưa có bữa ăn trong ngày này.',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    );
  }
}

class _JournalDeleteBackground extends StatelessWidget {
  const _JournalDeleteBackground({required this.dishName, super.key});

  final String dishName;

  @override
  Widget build(BuildContext context) {
    return Container(
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.only(right: 18),
      decoration: BoxDecoration(
        color: const Color(0xFFFFDDD7),
        border: Border.all(color: BalanceColors.ink, width: 2.2),
        borderRadius: BorderRadius.circular(12),
        boxShadow: const [
          BoxShadow(color: BalanceColors.ink, offset: Offset(4, 5)),
        ],
      ),
      child: Semantics(
        label: 'Vuốt để xoá $dishName',
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'XOÁ',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w900),
            ),
            SizedBox(width: 7),
            Icon(Icons.delete_outline_rounded, size: 25),
          ],
        ),
      ),
    );
  }
}

class _JournalDayOverview extends StatelessWidget {
  const _JournalDayOverview({
    required this.date,
    required this.entries,
    required this.calorieTarget,
  });

  final DateTime date;
  final List<JournalEntry> entries;
  final int calorieTarget;

  @override
  Widget build(BuildContext context) {
    final totals = _JournalDayTotals.fromEntries(entries);
    return SketchCard(
      key: const ValueKey('journal-day-overview'),
      radius: BalanceRadii.card,
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Tổng quan ngày',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
                ),
              ),
              Text(
                '${date.day}/${date.month}',
                style: const TextStyle(
                  color: BalanceColors.muted,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: RichText(
                  text: TextSpan(
                    style: const TextStyle(
                      fontFamily: 'Baloo 2',
                      color: BalanceColors.ink,
                    ),
                    children: [
                      TextSpan(
                        text: _format(totals.calories),
                        style: const TextStyle(
                          color: BalanceColors.blueDark,
                          fontSize: 30,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      TextSpan(
                        text:
                            ' kcal / ${_format(calorieTarget.toDouble())} kcal',
                        style: const TextStyle(
                          color: BalanceColors.muted,
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              _JournalCalorieRing(
                calories: totals.calories,
                target: calorieTarget,
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: _JournalMacro(
                  label: 'Đạm',
                  value: totals.protein,
                  color: const Color(0xFF218B37),
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _JournalMacro(
                  label: 'Carb',
                  value: totals.carbs,
                  color: BalanceColors.blueDark,
                ),
              ),
              const SizedBox(width: 7),
              Expanded(
                child: _JournalMacro(
                  label: 'Béo',
                  value: totals.fat,
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

class _JournalCalorieRing extends StatelessWidget {
  const _JournalCalorieRing({required this.calories, required this.target});

  final double calories;
  final int target;

  @override
  Widget build(BuildContext context) {
    final progress = target <= 0 ? 0.0 : (calories / target).clamp(0.0, 1.0);
    return SizedBox(
      width: 68,
      height: 68,
      child: Stack(
        fit: StackFit.expand,
        children: [
          CircularProgressIndicator(
            value: progress,
            strokeWidth: 7,
            strokeCap: StrokeCap.round,
            backgroundColor: const Color(0xFFE5E5E5),
            color: BalanceColors.blueDark,
          ),
          Center(
            child: Text(
              '${(progress * 100).round()}%',
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _JournalMacro extends StatelessWidget {
  const _JournalMacro({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 7),
      decoration: BoxDecoration(
        color: BalanceColors.paper,
        border: Border.all(color: BalanceColors.ink, width: 1.2),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: const TextStyle(
              color: BalanceColors.muted,
              fontWeight: FontWeight.w700,
            ),
          ),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(
              '${_format(value)} g',
              style: TextStyle(
                color: color,
                fontSize: 20,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MealSectionHeader extends StatelessWidget {
  const _MealSectionHeader({required this.onAdd});

  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const Expanded(
          child: Text(
            'Bữa ăn',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
          ),
        ),
        Semantics(
          button: true,
          label: 'Thêm món',
          child: InkWell(
            onTap: onAdd,
            borderRadius: BorderRadius.circular(10),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
              decoration: BoxDecoration(
                color: BalanceColors.paper,
                border: Border.all(color: BalanceColors.blueDark, width: 2),
                borderRadius: BorderRadius.circular(10),
                boxShadow: const [
                  BoxShadow(color: BalanceColors.ink, offset: Offset(2, 3)),
                ],
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.add_rounded,
                    color: BalanceColors.blueDark,
                    size: 19,
                  ),
                  SizedBox(width: 3),
                  Text(
                    'Thêm món',
                    style: TextStyle(
                      color: BalanceColors.blueDark,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _JournalEntryCard extends StatelessWidget {
  const _JournalEntryCard({required this.entry});

  final JournalEntry entry;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      radius: 14,
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 9),
      child: Row(
        children: [
          Container(
            width: 34,
            height: 34,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: _mealColor(entry.mealType).withValues(alpha: 0.14),
              shape: BoxShape.circle,
            ),
            child: Icon(
              _mealIcon(entry.mealType),
              color: _mealColor(entry.mealType),
              size: 22,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.mealType.label.replaceFirst('Bữa ', ''),
                  style: const TextStyle(
                    color: BalanceColors.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  entry.dishName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(
                  '${_format(entry.calories)} kcal',
                  style: const TextStyle(
                    color: BalanceColors.muted,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (StickerPaths.fileFor(entry.stickerPath) == null)
                  const Text(
                    'Chưa có sticker — món đã lưu trước khi tách nền',
                    style: TextStyle(color: BalanceColors.muted, fontSize: 11),
                  ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          StickerThumb(entry: entry, size: 56),
          const SizedBox(width: 3),
          const Tooltip(
            message: 'Vuốt sang trái để xoá',
            child: Icon(
              Icons.more_vert_rounded,
              color: BalanceColors.ink,
              size: 22,
            ),
          ),
        ],
      ),
    );
  }
}

class _JournalDayTotals {
  const _JournalDayTotals({
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  factory _JournalDayTotals.fromEntries(List<JournalEntry> entries) {
    return _JournalDayTotals(
      calories: entries.fold(0, (sum, item) => sum + item.calories),
      protein: entries.fold(0, (sum, item) => sum + item.proteinGrams),
      carbs: entries.fold(0, (sum, item) => sum + item.carbsGrams),
      fat: entries.fold(0, (sum, item) => sum + item.fatGrams),
    );
  }

  final double calories;
  final double protein;
  final double carbs;
  final double fat;
}

IconData _mealIcon(MealType type) => switch (type) {
  MealType.breakfast => Icons.wb_sunny_outlined,
  MealType.lunch => Icons.wb_sunny_rounded,
  MealType.dinner => Icons.nightlight_round,
  MealType.snack => Icons.cookie_outlined,
};

Color _mealColor(MealType type) => switch (type) {
  MealType.breakfast => BalanceColors.yellow,
  MealType.lunch => BalanceColors.orange,
  MealType.dinner => BalanceColors.blueDark,
  MealType.snack => BalanceColors.green,
};

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);
