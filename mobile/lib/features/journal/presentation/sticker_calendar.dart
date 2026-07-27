import 'package:balance/core/theme/balance_theme.dart';
import 'dart:io';

import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/domain/month_grid.dart';
import 'package:flutter/material.dart';

const _weekdayLabels = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

/// Lịch tháng dán sticker món ăn.
///
/// Mượn bố cục của app tham khảo (lưới tháng, sticker trong ô ngày, badge số
/// món) nhưng giữ nguyên chất sketch của Balance: viền mực dày, bóng cứng,
/// nền giấy — không dùng thẻ bo tròn đổ bóng nhoè.
class StickerCalendar extends StatelessWidget {
  const StickerCalendar({
    required this.month,
    required this.entries,
    required this.today,
    this.onDayTap,
    this.onMonthChanged,
    super.key,
  });

  final DateTime month;
  final List<JournalEntry> entries;
  final DateTime today;
  final ValueChanged<DateTime>? onDayTap;
  final ValueChanged<DateTime>? onMonthChanged;

  @override
  Widget build(BuildContext context) {
    final grouped = entriesByDay(entries);
    final cells = monthGridDays(month);
    return SketchCard(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _MonthHeader(month: month, onMonthChanged: onMonthChanged),
          const SizedBox(height: 10),
          Row(
            children: [
              for (final label in _weekdayLabels)
                Expanded(
                  child: Center(
                    child: Text(
                      label,
                      style: TextStyle(
                        fontWeight: FontWeight.w800,
                        fontSize: 12,
                        color: label == 'CN'
                            ? BalanceColors.orange
                            : BalanceColors.muted,
                      ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            padding: EdgeInsets.zero,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: daysPerWeek,
              mainAxisSpacing: 5,
              crossAxisSpacing: 5,
              childAspectRatio: 0.86,
            ),
            itemCount: cells.length,
            itemBuilder: (context, index) {
              final day = cells[index];
              if (day == null) return const SizedBox.shrink();
              final dayEntries = grouped[DayKey.from(day)] ?? const [];
              return _DayCell(
                day: day,
                entries: dayEntries,
                isToday: DayKey.from(day) == DayKey.from(today),
                onTap: onDayTap == null ? null : () => onDayTap!(day),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _MonthHeader extends StatelessWidget {
  const _MonthHeader({required this.month, required this.onMonthChanged});

  final DateTime month;
  final ValueChanged<DateTime>? onMonthChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _ArrowButton(
          icon: Icons.chevron_left_rounded,
          semanticLabel: 'Tháng trước',
          onPressed: onMonthChanged == null
              ? null
              : () => onMonthChanged!(DateTime(month.year, month.month - 1)),
        ),
        Expanded(
          child: Center(
            child: Text(
              'Tháng ${month.month}, ${month.year}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
        ),
        _ArrowButton(
          icon: Icons.chevron_right_rounded,
          semanticLabel: 'Tháng sau',
          onPressed: onMonthChanged == null
              ? null
              : () => onMonthChanged!(DateTime(month.year, month.month + 1)),
        ),
      ],
    );
  }
}

class _ArrowButton extends StatelessWidget {
  const _ArrowButton({
    required this.icon,
    required this.semanticLabel,
    required this.onPressed,
  });

  final IconData icon;
  final String semanticLabel;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semanticLabel,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            border: Border.all(color: BalanceColors.ink, width: 2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, size: 22),
        ),
      ),
    );
  }
}

class _DayCell extends StatelessWidget {
  const _DayCell({
    required this.day,
    required this.entries,
    required this.isToday,
    required this.onTap,
  });

  final DateTime day;
  final List<JournalEntry> entries;
  final bool isToday;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final hasMeals = entries.isNotEmpty;
    final files = entries
        .map((entry) => StickerPaths.fileFor(entry.stickerPath))
        .whereType<File>()
        .toList(growable: false);
    return Semantics(
      button: onTap != null,
      label: hasMeals
          ? 'Ngày ${day.day}, ${entries.length} món'
          : 'Ngày ${day.day}, chưa ghi món nào',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(9),
        child: Container(
          decoration: BoxDecoration(
            // Ngày có món dùng nền kem hồng để sticker viền trắng nổi lên;
            // ngày trống để nền giấy cho lưới đỡ nặng mắt.
            color: hasMeals ? BalanceColors.stickerMat : BalanceColors.paper,
            border: Border.all(
              color: isToday ? BalanceColors.blue : BalanceColors.ink,
              width: isToday ? 2.4 : 1.2,
            ),
            borderRadius: BorderRadius.circular(9),
          ),
          padding: const EdgeInsets.all(3),
          child: Column(
            children: [
              Text(
                '${day.day}',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: isToday ? BalanceColors.blueDark : BalanceColors.ink,
                ),
              ),
              Expanded(
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    Padding(
                      // Chừa chỗ cho badge ở góc dưới phải.
                      padding: EdgeInsets.only(
                        bottom: entries.length > 1 ? 7 : 0,
                      ),
                      child: files.isEmpty
                          // Có món nhưng chưa có sticker (bữa cũ, hoặc tách
                          // nền trượt): chấm tròn để ngày vẫn "có dấu".
                          ? (hasMeals && entries.length == 1
                                ? const Icon(
                                    Icons.circle,
                                    size: 8,
                                    color: BalanceColors.orange,
                                  )
                                : const SizedBox.shrink())
                          : _StickerRow(files: files),
                    ),
                    if (entries.length > 1)
                      Positioned(
                        right: 1,
                        bottom: 1,
                        child: _CountBadge(count: entries.length),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Nhiều món trong một ngày thì xếp thành một hàng ngang.
///
/// Hàng ngang đọc nhanh hơn kiểu xòe chồng lấn: trong ô lịch chỉ rộng chừng
/// 44pt, ảnh chồng nhau che mất nhau và mắt phải dừng lại giải mã.
class _StickerRow extends StatelessWidget {
  const _StickerRow({required this.files});

  final List<File> files;

  /// Tối đa ba ảnh; ăn nhiều hơn thì badge ×N phía dưới lo phần còn lại.
  static const maxShown = 3;

  @override
  Widget build(BuildContext context) {
    final shown = files.length <= maxShown ? files : files.sublist(0, maxShown);
    if (shown.length == 1) return _CellSticker(file: shown.first);
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        for (var i = 0; i < shown.length; i++) ...[
          if (i > 0) const SizedBox(width: 1),
          Expanded(child: _CellSticker(file: shown[i])),
        ],
      ],
    );
  }
}

class _CellSticker extends StatelessWidget {
  const _CellSticker({required this.file});

  final File file;

  @override
  Widget build(BuildContext context) {
    return Image.file(
      file,
      fit: BoxFit.contain,
      filterQuality: FilterQuality.medium,
      errorBuilder: (_, _, _) => const SizedBox.shrink(),
    );
  }
}

class _CountBadge extends StatelessWidget {
  const _CountBadge({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 0.5),
      decoration: BoxDecoration(
        color: BalanceColors.orange,
        border: Border.all(color: BalanceColors.ink, width: 1),
        borderRadius: BorderRadius.circular(99),
      ),
      child: Text(
        '×$count',
        maxLines: 1,
        style: const TextStyle(
          fontSize: 8.5,
          height: 1.15,
          fontWeight: FontWeight.w900,
          color: Colors.white,
        ),
      ),
    );
  }
}
