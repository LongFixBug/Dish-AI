import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/domain/month_grid.dart';
import 'package:balance/features/journal/domain/month_stats.dart';
import 'package:balance/features/journal/presentation/month_summary.dart';
import 'package:balance/features/journal/presentation/sticker_calendar.dart';
import 'package:balance/features/journal/presentation/sticker_thumb.dart';
import 'package:flutter/material.dart';

class JournalScreen extends StatefulWidget {
  const JournalScreen({this.now, super.key});

  /// Đồng hồ tiêm được cho test; bỏ trống thì lấy giờ máy.
  final DateTime? now;

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

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final today = _today;
    final selected = _selectedDay ?? today;
    final month = _visibleMonth ?? DateTime(today.year, today.month);
    final all = state?.journalEntries ?? const <JournalEntry>[];
    final monthEntries = entriesInMonth(all, month);
    final yearEntries = entriesInYear(all, month.year);
    final entries =
        entriesByDay(all)[DayKey.from(selected)] ?? const <JournalEntry>[];
    final isToday = DayKey.from(selected) == DayKey.from(today);
    return Scaffold(
      appBar: AppBar(
        title: Text(
          isToday
              ? 'Nhật ký hôm nay'
              : 'Nhật ký ${selected.day}/${selected.month}',
        ),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
      ),
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
                // Đống sticker là "ảnh bìa" của tháng — tự ẩn khi tháng
                // chưa có sticker nào nên không chiếm chỗ vô ích.
                MonthStickerPile(
                  key: ValueKey('pile-$_refreshToken-${month.month}'),
                  month: month,
                  entries: monthEntries,
                ),
                if (monthEntries.any(
                  (entry) => (entry.stickerPath ?? '').isNotEmpty,
                ))
                  const SizedBox(height: 16),
                Text(
                  'Tổng kết cả năm ${month.year}',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                YearStatsSection(year: month.year, entries: yearEntries),
                const SizedBox(height: 16),
                StickerCalendar(
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
                const SizedBox(height: 16),
                if (entries.isEmpty) const _EmptyDay(),
                if (entries.isNotEmpty) _JournalSummary(entries: entries),
                if (entries.isNotEmpty) const SizedBox(height: 16),
                for (final entry in entries)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Dismissible(
                      key: ValueKey(entry.id),
                      direction: DismissDirection.endToStart,
                      background: Container(
                        alignment: Alignment.centerRight,
                        padding: const EdgeInsets.only(right: 24),
                        color: Colors.redAccent,
                        child: const Icon(Icons.delete, color: Colors.white),
                      ),
                      onDismissed: (_) => state?.removeJournalEntry(entry.id),
                      child: _JournalEntryCard(entry: entry),
                    ),
                  ),
                const SizedBox(height: 10),
                Text(
                  'Tổng kết tháng ${month.month}, ${month.year} • '
                  'Năm: ${yearEntries.length} món',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 10),
                MonthStatsSection(month: month, entries: monthEntries),
              ],
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
      shadow: false,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      child: Row(
        children: [
          const Icon(Icons.no_meals_rounded, size: 26),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'Ngày này chưa có món nào.',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    );
  }
}

class _JournalSummary extends StatelessWidget {
  const _JournalSummary({required this.entries});

  final List<JournalEntry> entries;

  @override
  Widget build(BuildContext context) {
    final calories = entries.fold<double>(
      0,
      (sum, item) => sum + item.calories,
    );
    return SketchCard(
      color: BalanceColors.yellow,
      child: Column(
        children: [
          Text(
            '${entries.length} món • ${_format(calories)} kcal',
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 10),
          Center(child: StickerStrip(entries: entries)),
        ],
      ),
    );
  }
}

class _JournalEntryCard extends StatelessWidget {
  const _JournalEntryCard({required this.entry});

  final JournalEntry entry;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      child: Row(
        children: [
          StickerThumb(entry: entry, size: 46),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.dishName,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(
                  '${entry.mealType.label} • ${_format(entry.totalGrams)} g',
                ),
                if (StickerPaths.fileFor(entry.stickerPath) == null)
                  const Text(
                    'Chưa có sticker — món đã lưu trước khi tách nền',
                    style: TextStyle(color: BalanceColors.muted, fontSize: 11),
                  ),
              ],
            ),
          ),
          Text(
            '${_format(entry.calories)} kcal',
            style: const TextStyle(
              color: BalanceColors.blueDark,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);
