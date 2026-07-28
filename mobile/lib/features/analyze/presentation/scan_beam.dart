import 'dart:math' as math;
import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

/// Một vạch quét phẳng đi tới món ăn rồi uốn cong, tạo cảm giác máy quét ôm
/// theo chiều sâu của món thay vì phủ một hiệu ứng 3D lên cả tấm ảnh.
class ScanBeam extends StatefulWidget {
  const ScanBeam({
    required this.imageBytes,
    this.running = true,
    this.borderRadius = 16,
    this.fit = BoxFit.cover,
    this.fallback,
    super.key,
  });

  final Uint8List imageBytes;
  final bool running;
  final double borderRadius;
  final BoxFit fit;

  /// Hiện thay ảnh khi bytes không giải mã được.
  final Widget? fallback;

  @override
  State<ScanBeam> createState() => _ScanBeamState();
}

class _ScanBeamState extends State<ScanBeam>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _progress;
  bool _reduceMotion = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2600),
    );
    _progress = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOutCubic,
    );
    if (widget.running) _controller.repeat(reverse: true);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (_reduceMotion == reduceMotion) return;
    _reduceMotion = reduceMotion;
    _syncAnimation();
  }

  @override
  void didUpdateWidget(ScanBeam oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.running != oldWidget.running) _syncAnimation();
  }

  void _syncAnimation() {
    if (!widget.running) {
      _controller.stop();
      _controller.value = 0;
      return;
    }
    if (_reduceMotion) {
      _controller.stop();
      _controller.value = 0.56;
      return;
    }
    if (!_controller.isAnimating) _controller.repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(widget.borderRadius),
      child: widget.running
          ? Semantics(
              image: true,
              label: 'Đang quét chiều sâu món ăn',
              child: ExcludeSemantics(
                child: RepaintBoundary(
                  key: const ValueKey('scan-3d-reveal'),
                  child: AnimatedBuilder(
                    animation: _progress,
                    builder: (context, _) => ScanDepthFrame(
                      imageBytes: widget.imageBytes,
                      progress: _progress.value,
                      fit: widget.fit,
                      fallback: widget.fallback,
                    ),
                  ),
                ),
              ),
            )
          : _PhotoLayer(
              imageBytes: widget.imageBytes,
              fit: widget.fit,
              fallback: widget.fallback,
            ),
    );
  }
}

/// Một frame cố định của hiệu ứng, tách khỏi controller để test/golden ổn định.
class ScanDepthFrame extends StatelessWidget {
  const ScanDepthFrame({
    required this.imageBytes,
    required this.progress,
    this.fit = BoxFit.cover,
    this.fallback,
    super.key,
  });

  final Uint8List imageBytes;
  final double progress;
  final BoxFit fit;
  final Widget? fallback;

  @override
  Widget build(BuildContext context) {
    final scanProgress = progress.clamp(0.0, 1.0).toDouble();
    final isAcrossFood = _ScanLine.isAcrossFood(scanProgress);

    return Stack(
      fit: StackFit.expand,
      children: [
        _PhotoLayer(imageBytes: imageBytes, fit: fit, fallback: fallback),
        if (isAcrossFood) ...[
          const ColoredBox(color: Color(0x1A061426)),
          CustomPaint(painter: _DepthShadowPainter(progress: scanProgress)),
        ],
        CustomPaint(
          key: ValueKey(isAcrossFood ? 'scan-3d-arc' : 'scan-flat-beam'),
          painter: isAcrossFood
              ? _CurvedScanPainter(progress: scanProgress)
              : _FlatScanPainter(progress: scanProgress),
        ),
      ],
    );
  }
}

class _PhotoLayer extends StatelessWidget {
  const _PhotoLayer({
    required this.imageBytes,
    required this.fit,
    this.fallback,
  });

  final Uint8List imageBytes;
  final BoxFit fit;
  final Widget? fallback;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: BalanceColors.paper,
      child: Image.memory(
        imageBytes,
        fit: fit,
        gaplessPlayback: true,
        filterQuality: FilterQuality.high,
        errorBuilder: (_, _, _) =>
            fallback ?? const ColoredBox(color: Color(0xFFCAD9E7)),
      ),
    );
  }
}

class _DepthShadowPainter extends CustomPainter {
  const _DepthShadowPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final line = _ScanLine.from(size, progress);
    canvas.drawPath(
      line.path(offsetY: 10),
      Paint()
        ..color = Colors.black.withValues(alpha: 0.34)
        ..strokeWidth = 17
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12),
    );
  }

  @override
  bool shouldRepaint(_DepthShadowPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _FlatScanPainter extends CustomPainter {
  const _FlatScanPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final line = _ScanLine.from(size, progress);
    final beam = line.path();
    canvas.drawPath(
      beam,
      Paint()
        ..color = const Color(0xFF23D8FF).withValues(alpha: 0.78)
        ..strokeWidth = 11
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8),
    );
    canvas.drawPath(
      beam,
      Paint()
        ..color = Colors.white.withValues(alpha: 0.94)
        ..strokeWidth = 2.8
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(_FlatScanPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _CurvedScanPainter extends CustomPainter {
  const _CurvedScanPainter({required this.progress});

  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final line = _ScanLine.from(size, progress);
    _paintScanPlane(canvas, size, line);
    _paintGrid(canvas, size, line);
    _paintBeam(canvas, line);
  }

  void _paintScanPlane(Canvas canvas, Size size, _ScanLine line) {
    const planeDepth = 42.0;
    final plane = Path()
      ..moveTo(0, line.centerY - planeDepth)
      ..quadraticBezierTo(
        size.width / 2,
        line.controlY - planeDepth * 0.45,
        size.width,
        line.centerY - planeDepth,
      )
      ..lineTo(size.width, line.centerY)
      ..quadraticBezierTo(size.width / 2, line.controlY, 0, line.centerY)
      ..close();
    final bounds = Rect.fromLTWH(
      0,
      line.centerY - planeDepth - line.curveDepth,
      size.width,
      planeDepth + line.curveDepth,
    );
    canvas.drawPath(
      plane,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0x001CD8FF), Color(0x514F91F7), Color(0xB323D8FF)],
        ).createShader(bounds),
    );
  }

  void _paintGrid(Canvas canvas, Size size, _ScanLine line) {
    const planeDepth = 42.0;
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.34)
      ..strokeWidth = 0.9
      ..style = PaintingStyle.stroke;

    for (var index = 0; index <= 8; index++) {
      final fraction = index / 8;
      canvas.drawLine(
        line.pointAt(size, fraction, offsetY: -planeDepth, curveScale: 0.45),
        line.pointAt(size, fraction),
        paint,
      );
    }

    for (var index = 1; index <= 2; index++) {
      final depthFraction = index / 3;
      final offsetY = -planeDepth * (1 - depthFraction);
      canvas.drawPath(line.path(offsetY: offsetY, curveScale: 0.45), paint);
    }
  }

  void _paintBeam(Canvas canvas, _ScanLine line) {
    final beam = line.path();
    canvas.drawPath(
      beam,
      Paint()
        ..color = const Color(0xFF23D8FF).withValues(alpha: 0.9)
        ..strokeWidth = 14
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 10),
    );
    canvas.drawPath(
      beam,
      Paint()
        ..color = Colors.white
        ..strokeWidth = 3.1
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke,
    );
    canvas.drawPath(
      beam,
      Paint()
        ..color = BalanceColors.blueDark
        ..strokeWidth = 1.2
        ..strokeCap = StrokeCap.round
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(_CurvedScanPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _ScanLine {
  const _ScanLine({
    required this.width,
    required this.centerY,
    required this.curveDepth,
  });

  static const _foodEntry = 0.32;
  static const _foodExit = 0.76;

  final double width;
  final double centerY;
  final double curveDepth;

  double get controlY => centerY - curveDepth * 2;

  static bool isAcrossFood(double progress) =>
      progress > _foodEntry && progress < _foodExit;

  factory _ScanLine.from(Size size, double progress) {
    final travel = size.height + 64;
    final centerY = -32 + travel * progress;
    final zoneProgress = ((progress - _foodEntry) / (_foodExit - _foodEntry))
        .clamp(0.0, 1.0);
    final curveDepth =
        math.sin(zoneProgress * math.pi) * math.min(34.0, size.height * 0.08);
    return _ScanLine(
      width: size.width,
      centerY: centerY,
      curveDepth: curveDepth,
    );
  }

  Path path({double offsetY = 0, double curveScale = 1}) {
    return Path()
      ..moveTo(0, centerY + offsetY)
      ..quadraticBezierTo(
        width / 2,
        centerY - curveDepth * curveScale * 2 + offsetY,
        width,
        centerY + offsetY,
      );
  }

  Offset pointAt(
    Size size,
    double fraction, {
    double offsetY = 0,
    double curveScale = 1,
  }) {
    final t = fraction.clamp(0.0, 1.0);
    final y = centerY - curveDepth * curveScale * 4 * t * (1 - t) + offsetY;
    return Offset(size.width * t, y);
  }
}
