import 'dart:io';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/domain/month_grid.dart';
import 'package:balance/features/journal/domain/month_stats.dart';
import 'package:balance/features/journal/domain/sticker_physics.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

/// Đống sticker của cả tháng — mượn ý "bàn ăn tổng kết" của app tham khảo,
/// vẽ bằng chất sketch của Balance: khung viền mực, bóng cứng, nền kem hồng.
///
/// Vị trí từng sticker sinh từ seed theo tháng nên dựng lại bao nhiêu lần
/// cũng nằm yên một chỗ; sang tháng khác mới đổi thế trận.
class MonthStickerPile extends StatefulWidget {
  const MonthStickerPile({
    required this.month,
    required this.entries,
    this.height = 190,
    this.animate = true,
    super.key,
  });

  final DateTime month;
  final List<JournalEntry> entries;
  final double height;

  /// Tắt trong test/golden để khung đứng yên ngay ở khung hình đầu.
  final bool animate;

  /// Quá đông thì đống ảnh thành bãi rác — lấy các bữa gần nhất là đủ kể chuyện.
  static const int maxStickers = 30;

  @override
  State<MonthStickerPile> createState() => _MonthStickerPileState();
}

class _MonthStickerPileState extends State<MonthStickerPile>
    with SingleTickerProviderStateMixin {
  Ticker? _ticker;
  StickerWorld? _world;
  Size _area = Size.zero;
  Duration _last = Duration.zero;

  @override
  void dispose() {
    _ticker?.dispose();
    super.dispose();
  }

  void _rebuildWorld(Size area, int count) {
    _area = area;
    _world = buildStickerWorld(
      count: count,
      seed: pileSeed(widget.month),
      width: area.width,
      height: area.height,
      stickerSize: fillingStickerSize(
        count: count,
        width: area.width,
        height: area.height,
      ),
    );
    if (!widget.animate) {
      // Golden/widget test: chạy thẳng tới trạng thái đã nằm yên.
      for (var i = 0; i < 900; i++) {
        _world!.step(1 / 60);
      }
      return;
    }
    _last = Duration.zero;
    _ticker?.dispose();
    _ticker = createTicker(_onTick)..start();
  }

  void _onTick(Duration elapsed) {
    final world = _world;
    if (world == null) return;
    // Kẹp bước thời gian: khi app bị treo hoặc chuyển tab, elapsed nhảy một
    // phát rất lớn và mô phỏng sẽ cho sticker xuyên thẳng qua đáy.
    final dt = ((elapsed - _last).inMicroseconds / 1e6).clamp(0.0, 1 / 30);
    _last = elapsed;
    if (dt <= 0) return;
    world.step(dt);
    if (world.isSettled) {
      _ticker?.stop();
    }
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final files = widget.entries
        .map((entry) => StickerPaths.fileFor(entry.stickerPath))
        .whereType<File>()
        .toList(growable: false);
    if (files.isEmpty) return const SizedBox.shrink();

    final shown = files.length <= MonthStickerPile.maxStickers
        ? files
        : files.sublist(files.length - MonthStickerPile.maxStickers);
    return SketchCard(
      padding: EdgeInsets.zero,
      color: BalanceColors.stickerMat,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: SizedBox(
          height: widget.height,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final area = constraints.biggest;
              if (_world == null ||
                  _area != area ||
                  _world!.bodies.length != shown.length) {
                // Dựng lại trong khung dựng thì setState là thừa và bị cấm;
                // gọi thẳng vì chính lần dựng này sẽ vẽ trạng thái mới.
                _rebuildWorld(area, shown.length);
              }
              final bodies = _world!.bodies;
              return Stack(
                clipBehavior: Clip.hardEdge,
                children: [
                  for (var i = 0; i < bodies.length && i < shown.length; i++)
                    Positioned(
                      left: bodies[i].left,
                      top: bodies[i].top,
                      child: Transform.rotate(
                        angle: bodies[i].angle,
                        child: Image.file(
                          shown[i],
                          width: bodies[i].size,
                          height: bodies[i].size,
                          fit: BoxFit.contain,
                          filterQuality: FilterQuality.medium,
                          errorBuilder: (_, _, _) => const SizedBox.shrink(),
                        ),
                      ),
                    ),
                  Positioned(
                    left: 10,
                    bottom: 8,
                    child: _PileCaption(count: widget.entries.length),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _PileCaption extends StatelessWidget {
  const _PileCaption({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: BalanceColors.paper,
        border: Border.all(color: BalanceColors.ink, width: 1.6),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        '$count món tháng này',
        style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800),
      ),
    );
  }
}

/// Cụm thẻ thống kê tháng: tổng món / tổng kcal / trung bình, món phổ biến
/// nhất và biểu đồ món theo tuần. Trục là món ăn và kcal — Balance là app
/// dinh dưỡng, không phải sổ chi tiêu.
class MonthStatsSection extends StatelessWidget {
  const MonthStatsSection({
    required this.month,
    required this.entries,
    super.key,
  });

  final DateTime month;
  final List<JournalEntry> entries;

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) {
      return SketchCard(
        shadow: false,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
        child: Row(
          children: [
            const Icon(Icons.bar_chart_rounded, size: 26),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Chưa có món nào trong tháng ${month.month}.',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          ],
        ),
      );
    }

    final totals = monthTotals(entries);
    final popular = mostFrequentDish(entries);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Expanded(
              child: _StatTile(
                label: 'Tổng món',
                value: '${totals.totalMeals}',
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _StatTile(
                label: 'Tổng kcal',
                value: _formatKcal(totals.totalCalories),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _StatTile(
                label: 'TB/món',
                value: _formatKcal(totals.averageCalories),
              ),
            ),
          ],
        ),
        // ×1 thì "phổ biến nhất" là câu vô nghĩa — mọi món đều mới ăn một
        // lần, chưa có gì để nói. Chờ tới khi thật sự có món lặp lại.
        if (popular != null && popular.count > 1) ...[
          const SizedBox(height: 12),
          _PopularDishCard(
            dishName: popular.dishName,
            count: popular.count,
            entries: entries,
          ),
        ],
        const SizedBox(height: 12),
        _WeeklyBars(counts: weeklyMealCounts(month, entries)),
      ],
    );
  }
}

/// Tổng kết cả năm đang chứa tháng được chọn.
class YearStatsSection extends StatelessWidget {
  const YearStatsSection({
    required this.year,
    required this.entries,
    super.key,
  });

  final int year;
  final List<JournalEntry> entries;

  @override
  Widget build(BuildContext context) {
    final totals = yearTotals(entries);
    return SketchCard(
      color: BalanceColors.paperBlue,
      shadow: false,
      child: Row(
        children: [
          Expanded(
            child: _StatTile(
              label: 'Tổng món năm $year',
              value: '${totals.totalMeals}',
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _StatTile(
              label: 'Tổng kcal năm',
              value: _formatKcal(totals.totalCalories),
            ),
          ),
        ],
      ),
    );
  }
}

String _formatKcal(double value) {
  if (value >= 10000) return '${(value / 1000).toStringAsFixed(1)}k';
  return value.round().toString();
}

class _StatTile extends StatelessWidget {
  const _StatTile({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      shadow: false,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 12),
      child: Column(
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: BalanceColors.muted,
            ),
          ),
          const SizedBox(height: 4),
          FittedBox(
            child: Text(
              value,
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

class _PopularDishCard extends StatelessWidget {
  const _PopularDishCard({
    required this.dishName,
    required this.count,
    required this.entries,
  });

  final String dishName;
  final int count;
  final List<JournalEntry> entries;

  File? get _stickerFile {
    for (final entry in entries) {
      if (entry.dishName != dishName) continue;
      final file = StickerPaths.fileFor(entry.stickerPath);
      if (file != null) return file;
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final file = _stickerFile;
    return SketchCard(
      shadow: false,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          Container(
            width: 52,
            height: 52,
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(
              color: BalanceColors.stickerMat,
              border: Border.all(color: BalanceColors.ink, width: 1.4),
              borderRadius: BorderRadius.circular(10),
            ),
            child: file != null
                ? Image.file(
                    file,
                    fit: BoxFit.contain,
                    errorBuilder: (_, _, _) =>
                        const Icon(Icons.restaurant_rounded, size: 24),
                  )
                : const Icon(Icons.restaurant_rounded, size: 24),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Phổ biến nhất',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: BalanceColors.muted,
                  ),
                ),
                Text(
                  dishName,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '×$count',
            style: const TextStyle(
              fontSize: 19,
              fontWeight: FontWeight.w900,
              color: BalanceColors.orange,
            ),
          ),
        ],
      ),
    );
  }
}

class _WeeklyBars extends StatelessWidget {
  const _WeeklyBars({required this.counts});

  final List<int> counts;

  @override
  Widget build(BuildContext context) {
    final maxCount = counts.fold<int>(
      1,
      (max, value) => value > max ? value : max,
    );
    return SketchCard(
      shadow: false,
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Món theo tuần', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          SizedBox(
            height: 108,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                for (var week = 0; week < counts.length; week++) ...[
                  if (week > 0) const SizedBox(width: 10),
                  Expanded(
                    child: _WeekBar(
                      label: 'Tuần ${week + 1}',
                      count: counts[week],
                      fraction: counts[week] / maxCount,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _WeekBar extends StatelessWidget {
  const _WeekBar({
    required this.label,
    required this.count,
    required this.fraction,
  });

  final String label;
  final int count;
  final double fraction;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Text(
          '$count',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 3),
        // Tuần 0 món vẫn hiện một vạch mỏng: cột biến mất hẳn đọc như lỗi
        // dữ liệu chứ không phải "tuần đó nhịn ghi".
        FractionallySizedBox(
          widthFactor: 1,
          child: Container(
            height: 4 + 62 * fraction,
            decoration: BoxDecoration(
              color: count == 0 ? BalanceColors.paperBlue : BalanceColors.blue,
              border: Border.all(color: BalanceColors.ink, width: 1.4),
              borderRadius: const BorderRadius.vertical(
                top: Radius.circular(5),
              ),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: const TextStyle(
            fontSize: 11,
            fontWeight: FontWeight.w700,
            color: BalanceColors.muted,
          ),
        ),
      ],
    );
  }
}
