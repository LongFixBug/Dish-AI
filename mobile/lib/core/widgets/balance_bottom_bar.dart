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
    return SizedBox(
      height: 92,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.topCenter,
        children: [
          Positioned(
            left: 14,
            right: 14,
            bottom: 8,
            child: Container(
              height: 68,
              decoration: BoxDecoration(
                color: BalanceColors.paper,
                border: Border.all(color: BalanceColors.ink, width: 2.5),
                borderRadius: BorderRadius.circular(10),
                boxShadow: const [
                  BoxShadow(color: BalanceColors.ink, offset: Offset(4, 5)),
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
                  padding: const EdgeInsets.all(5),
                  decoration: BoxDecoration(
                    color: BalanceColors.paper,
                    shape: BoxShape.circle,
                    border: Border.all(color: BalanceColors.ink, width: 2.5),
                    boxShadow: const [
                      BoxShadow(color: BalanceColors.ink, offset: Offset(3, 4)),
                    ],
                  ),
                  child: Container(
                    decoration: const BoxDecoration(
                      color: BalanceColors.blue,
                      shape: BoxShape.circle,
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
    final color = selected ? Colors.white : BalanceColors.ink;
    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(7),
        child: Container(
          height: double.infinity,
          decoration: BoxDecoration(
            color: selected ? BalanceColors.blue : Colors.transparent,
            borderRadius: BorderRadius.circular(7),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: color, size: 25),
              Text(
                label,
                maxLines: 1,
                style: TextStyle(
                  color: color,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
