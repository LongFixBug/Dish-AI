import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class SketchCard extends StatelessWidget {
  const SketchCard({
    required this.child,
    this.color = BalanceColors.paper,
    this.padding = const EdgeInsets.all(16),
    this.radius = 12,
    this.shadow = true,
    super.key,
  });

  final Widget child;
  final Color color;
  final EdgeInsetsGeometry padding;
  final double radius;
  final bool shadow;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color,
        border: Border.all(color: BalanceColors.ink, width: 2.2),
        borderRadius: BorderRadius.circular(radius),
        boxShadow: shadow
            ? const [BoxShadow(color: BalanceColors.ink, offset: Offset(4, 5))]
            : null,
      ),
      child: child,
    );
  }
}
