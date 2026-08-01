import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class BalanceBottomBar extends StatelessWidget {
  const BalanceBottomBar({
    this.currentIndex = 0,
    this.onHomePressed,
    this.onJournalPressed,
    this.onCameraPressed,
    this.onSuggestionsPressed,
    this.onProfilePressed,
    super.key,
  });

  final int currentIndex;
  final VoidCallback? onHomePressed;
  final VoidCallback? onJournalPressed;
  final VoidCallback? onCameraPressed;
  final VoidCallback? onSuggestionsPressed;
  final VoidCallback? onProfilePressed;

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    return SizedBox(
      height: 96,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.topCenter,
        children: [
          Positioned(
            left: 14,
            right: 14,
            bottom: 10,
            child: Container(
              height: 70,
              decoration: BoxDecoration(
                color: palette.surface,
                border: Border.all(
                  color: palette.ink,
                  width: BalanceStrokes.strong,
                ),
                borderRadius: BorderRadius.circular(BalanceRadii.card),
                boxShadow: [
                  BoxShadow(
                    color: palette.shadow,
                    offset: const Offset(4, 5),
                    blurRadius: 0,
                  ),
                ],
              ),
              child: Row(
                children: [
                  _NavItem(
                    label: 'Trang chủ',
                    icon: Icons.home_rounded,
                    selected: currentIndex == 0,
                    onTap: onHomePressed,
                  ),
                  _NavItem(
                    label: 'Nhật ký',
                    icon: Icons.menu_book_rounded,
                    selected: currentIndex == 1,
                    onTap: onJournalPressed,
                  ),
                  const SizedBox(width: 74),
                  _NavItem(
                    label: 'Gợi ý',
                    icon: Icons.lightbulb_outline_rounded,
                    selected: currentIndex == 3,
                    onTap: onSuggestionsPressed,
                  ),
                  _NavItem(
                    label: 'Tôi',
                    icon: Icons.person_outline_rounded,
                    selected: currentIndex == 4,
                    onTap: onProfilePressed,
                  ),
                ],
              ),
            ),
          ),
          Positioned(
            top: 0,
            child: Semantics(
              button: true,
              label: 'Chụp món ăn',
              child: GestureDetector(
                onTap: onCameraPressed,
                child: Container(
                  width: 72,
                  height: 72,
                  padding: const EdgeInsets.all(6),
                  decoration: BoxDecoration(
                    color: palette.surface,
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: palette.ink,
                      width: BalanceStrokes.strong,
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: palette.shadow,
                        offset: const Offset(4, 5),
                        blurRadius: 0,
                      ),
                    ],
                  ),
                  child: Container(
                    decoration: BoxDecoration(
                      color: palette.primary,
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.72),
                        width: 1.5,
                      ),
                    ),
                    child: const Icon(
                      Icons.camera_alt_rounded,
                      color: Colors.white,
                      size: 31,
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.label,
    required this.icon,
    required this.selected,
    this.onTap,
  });

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    final color = selected ? palette.primaryDark : palette.muted;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(7),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          curve: Curves.easeOutCubic,
          height: double.infinity,
          margin: const EdgeInsets.symmetric(horizontal: 3, vertical: 7),
          decoration: BoxDecoration(
            color: selected
                ? palette.primary.withValues(alpha: 0.14)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(BalanceRadii.small),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              AnimatedScale(
                duration: const Duration(milliseconds: 160),
                curve: Curves.easeOutCubic,
                scale: selected ? 1.08 : 1,
                child: Icon(icon, color: color, size: 25),
              ),
              AnimatedDefaultTextStyle(
                duration: const Duration(milliseconds: 220),
                style: TextStyle(
                  color: color,
                  fontSize: 10.5,
                  fontWeight: selected ? FontWeight.w900 : FontWeight.w700,
                ),
                child: Text(label, maxLines: 1),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
