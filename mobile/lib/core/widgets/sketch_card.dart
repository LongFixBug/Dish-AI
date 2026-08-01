import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class SketchCard extends StatelessWidget {
  const SketchCard({
    required this.child,
    this.color,
    this.padding = const EdgeInsets.all(16),
    this.radius = BalanceRadii.card,
    this.shadow = true,
    super.key,
  });

  final Widget child;
  final Color? color;
  final EdgeInsetsGeometry padding;
  final double radius;
  final bool shadow;

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? palette.surface,
        border: Border.all(color: palette.ink, width: BalanceStrokes.strong),
        borderRadius: BorderRadius.circular(radius),
        boxShadow: shadow
            ? [
                BoxShadow(
                  color: palette.shadow,
                  offset: const Offset(4, 5),
                  blurRadius: 0,
                ),
              ]
            : null,
      ),
      child: child,
    );
  }
}
