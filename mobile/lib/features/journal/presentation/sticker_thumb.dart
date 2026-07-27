import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:flutter/material.dart';

/// Ảnh sticker của một bữa ăn, bo trong ô nền kem hồng.
///
/// Sticker có viền TRẮNG nên phải đặt trên nền kem hồng mới thấy đường viền;
/// đặt lên nền giấy (gần trắng) là viền tàng hình.
class StickerThumb extends StatelessWidget {
  const StickerThumb({
    required this.entry,
    this.size = 44,
    this.fallbackIcon = Icons.restaurant_rounded,
    super.key,
  });

  final JournalEntry entry;
  final double size;
  final IconData fallbackIcon;

  @override
  Widget build(BuildContext context) {
    final file = StickerPaths.fileFor(entry.stickerPath);
    return Container(
      width: size,
      height: size,
      padding: EdgeInsets.all(size * 0.06),
      decoration: BoxDecoration(
        color: BalanceColors.stickerMat,
        border: Border.all(color: BalanceColors.ink, width: 1.4),
        borderRadius: BorderRadius.circular(size * 0.24),
      ),
      child: file == null
          ? Icon(fallbackIcon, size: size * 0.5, color: BalanceColors.ink)
          : Image.file(
              file,
              fit: BoxFit.contain,
              filterQuality: FilterQuality.medium,
              errorBuilder: (_, _, _) => Icon(
                fallbackIcon,
                size: size * 0.5,
                color: BalanceColors.ink,
              ),
            ),
    );
  }
}

/// Hàng sticker của các bữa trong một khoảng thời gian, có chồng mép nhau.
class StickerStrip extends StatelessWidget {
  const StickerStrip({
    required this.entries,
    this.size = 34,
    this.maxShown = 8,
    super.key,
  });

  final List<JournalEntry> entries;
  final double size;
  final int maxShown;

  @override
  Widget build(BuildContext context) {
    final shown = entries.length <= maxShown
        ? entries
        : entries.sublist(0, maxShown);
    if (shown.isEmpty) return const SizedBox.shrink();
    // Chồng mép nhau cho hàng gọn lại và ra dáng "xâu" hơn là dãy ô rời rạc.
    final step = size * 0.74;
    return SizedBox(
      height: size,
      width: step * (shown.length - 1) + size,
      child: Stack(
        children: [
          for (var i = 0; i < shown.length; i++)
            Positioned(
              left: step * i,
              child: StickerThumb(entry: shown[i], size: size),
            ),
        ],
      ),
    );
  }
}
