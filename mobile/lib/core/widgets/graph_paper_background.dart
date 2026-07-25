import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class GraphPaperBackground extends StatelessWidget {
  const GraphPaperBackground({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: BalanceColors.paperBlue,
      child: CustomPaint(painter: const _GraphPaperPainter(), child: child),
    );
  }
}

class _GraphPaperPainter extends CustomPainter {
  const _GraphPaperPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final minorPaint = Paint()
      ..color = BalanceColors.blue.withValues(alpha: 0.10)
      ..strokeWidth = 1;
    final majorPaint = Paint()
      ..color = BalanceColors.blueDark.withValues(alpha: 0.16)
      ..strokeWidth = 1.2;

    const spacing = 24.0;
    for (var x = 0.0; x <= size.width; x += spacing) {
      final paint = x % (spacing * 4) == 0 ? majorPaint : minorPaint;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (var y = 0.0; y <= size.height; y += spacing) {
      final paint = y % (spacing * 4) == 0 ? majorPaint : minorPaint;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
