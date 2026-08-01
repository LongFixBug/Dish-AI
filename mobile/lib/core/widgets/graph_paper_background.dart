import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

/// Compatibility name used by the existing feature screens.
///
/// The actual three-layer notebook surface lives in
/// [NotebookAnimatedBackground]: grid, blue ribbon, then opaque app content.
class GraphPaperBackground extends StatelessWidget {
  const GraphPaperBackground({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return NotebookAnimatedBackground(child: child);
  }
}

/// The shared Balance notebook surface.
///
/// The ribbon is deliberately isolated in its own repaint boundary so its
/// slow animation never rebuilds a scrolling screen or its cards.
class NotebookAnimatedBackground extends StatefulWidget {
  const NotebookAnimatedBackground({required this.child, super.key});

  final Widget child;

  @override
  State<NotebookAnimatedBackground> createState() =>
      _NotebookAnimatedBackgroundState();
}

/// Turns the ribbon loop on only for the real app entrypoint. Tests can keep a
/// deterministic frame while still verifying the rendered background.
class BalanceMotionScope extends InheritedWidget {
  const BalanceMotionScope({
    required this.enabled,
    required super.child,
    super.key,
  });

  final bool enabled;

  static bool enabledOf(BuildContext context) {
    return context
            .dependOnInheritedWidgetOfExactType<BalanceMotionScope>()
            ?.enabled ??
        false;
  }

  @override
  bool updateShouldNotify(covariant BalanceMotionScope oldWidget) {
    return oldWidget.enabled != enabled;
  }
}

class _NotebookAnimatedBackgroundState extends State<NotebookAnimatedBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: BlueRibbonPainter.cycleDuration,
  );
  late final int _motionSeed =
      DateTime.now().microsecondsSinceEpoch & 0x7fffffff;
  bool? _animationAllowed;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final reduceMotion =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final allowed =
        BalanceMotionScope.enabledOf(context) &&
        !reduceMotion &&
        TickerMode.valuesOf(context).enabled;
    if (_animationAllowed == allowed) return;
    _animationAllowed = allowed;
    if (allowed) {
      _controller.repeat();
    } else {
      _controller
        ..stop()
        ..value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    final gridOpacity = Theme.of(context).brightness == Brightness.dark
        ? 0.42
        : 0.36;
    final motionSeed = _animationAllowed == true
        ? _motionSeed
        : BlueRibbonPainter.fixedTestSeed;
    return ColoredBox(
      color: palette.background,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Positioned.fill(
            child: RepaintBoundary(
              child: CustomPaint(
                painter: NotebookGridPainter(
                  gridColor: palette.grid,
                  opacity: gridOpacity,
                ),
              ),
            ),
          ),
          Positioned.fill(
            child: IgnorePointer(
              child: RepaintBoundary(
                child: AnimatedBuilder(
                  animation: _controller,
                  builder: (context, _) => CustomPaint(
                    painter: BlueRibbonPainter(
                      progress: _animationAllowed == true
                          ? _controller.value
                          : BlueRibbonPainter.staticPreviewProgress,
                      ribbonColor: palette.primary,
                      inkColor: palette.ink,
                      secondaryColor: palette.secondary,
                      successColor: palette.success,
                      warningColor: palette.warning,
                      motionSeed: motionSeed,
                    ),
                  ),
                ),
              ),
            ),
          ),
          Positioned.fill(child: widget.child),
        ],
      ),
    );
  }
}

/// Paints the notebook grid only. Keeping it separate makes the static layer
/// cheap when the blue ribbon repaints above it.
class NotebookGridPainter extends CustomPainter {
  const NotebookGridPainter({
    this.gridColor = BalanceColors.grid,
    this.opacity = 0.36,
  });

  final Color gridColor;
  final double opacity;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = gridColor.withValues(alpha: opacity)
      ..strokeWidth = 0.85;
    const spacing = 22.0;
    for (var x = 0.0; x <= size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (var y = 0.0; y <= size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant NotebookGridPainter oldDelegate) {
    return oldDelegate.gridColor != gridColor || oldDelegate.opacity != opacity;
  }
}

/// A single, thick marker line that glides in to hunt one apple at a time.
///
/// Every pass begins and ends outside the screen. The line passes through the
/// apple, exits, then a fresh apple appears shortly before the next pass. It
/// intentionally has no visual head, tail, or body segments: the whole stroke
/// reads as one alive, continuous gesture.
class BlueRibbonPainter extends CustomPainter {
  const BlueRibbonPainter({
    required this.progress,
    this.ribbonColor = BalanceColors.blue,
    this.inkColor = BalanceColors.ink,
    this.secondaryColor = BalanceColors.yellow,
    this.successColor = BalanceColors.green,
    this.warningColor = BalanceColors.orange,
    this.leafColor = BalanceColors.darkGreen,
    this.motionSeed = fixedTestSeed,
  });

  static const fixedTestSeed = 0xBA1AACE;
  /// A composed, non-empty frame for screens that deliberately disable
  /// animation (including golden tests and reduced-motion users).
  static const staticPreviewProgress = 0.56;
  static const cycleDuration = Duration(seconds: 11);
  static const _appleReturnsAt = 0.9;
  final double progress;
  final Color ribbonColor;
  final Color inkColor;
  final Color secondaryColor;
  final Color successColor;
  final Color warningColor;
  final Color leafColor;
  final int motionSeed;

  static List<Offset> routePoints(Size size, {int motionSeed = fixedTestSeed}) {
    return _SnakeHuntPath.generate(size, motionSeed).waypoints;
  }

  /// Compatibility helper for callers that need the deterministic path.
  static List<Offset> controlPoints(
    Size size,
    double progress, {
    int motionSeed = fixedTestSeed,
  }) {
    return routePoints(size, motionSeed: motionSeed);
  }

  static Offset snakePosition(
    Size size,
    double progress, {
    int motionSeed = fixedTestSeed,
  }) {
    final path = _SnakeHuntPath.generate(size, motionSeed);
    return path.sampleAt(path.totalLength * progress.clamp(0.0, 1.0)).position;
  }

  /// Kept as an alias for existing callers; it no longer implies a separate
  /// visual head.
  static Offset headPosition(
    Size size,
    double progress, {
    int motionSeed = fixedTestSeed,
  }) => snakePosition(size, progress, motionSeed: motionSeed);

  static Offset applePosition(Size size, {int motionSeed = fixedTestSeed}) =>
      _SnakeHuntPath.generate(size, motionSeed).apple;

  static double appleProgress(Size size, {int motionSeed = fixedTestSeed}) {
    final path = _SnakeHuntPath.generate(size, motionSeed);
    return path.appleDistance / path.totalLength;
  }

  static bool appleIsVisible(
    Size size,
    double progress, {
    int motionSeed = fixedTestSeed,
  }) {
    final phase = progress.clamp(0.0, 1.0);
    return phase < appleProgress(size, motionSeed: motionSeed) ||
        phase >= _appleReturnsAt;
  }

  static double _noise(int seed, int frame, int salt) {
    var value = seed ^ (frame * 0x45d9f3b) ^ (salt * 0x27d4eb2d) ^ 0x9e3779b9;
    value = (value ^ (value >> 16)) * 0x7feb352d;
    value = (value ^ (value >> 15)) * 0x846ca68b;
    value = value ^ (value >> 16);
    return (value & 0xfffffff) / 0xfffffff;
  }

  static double _lerp(double a, double b, double t) {
    return a + (b - a) * t;
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final path = _SnakeHuntPath.generate(size, motionSeed);
    final phase = progress.clamp(0.0, 1.0);
    final distance = path.totalLength * phase;
    final width = (size.shortestSide * 0.07).clamp(24.0, 44.0).toDouble();
    final trailLength = path.totalLength * 0.31;
    _paintApple(canvas, path, phase);

    final stroke = path.slice(
      (distance - trailLength).clamp(0.0, distance),
      distance,
    );
    final paint = Paint()
      ..color = ribbonColor.withValues(alpha: 0.86)
      ..style = PaintingStyle.stroke
      ..strokeWidth = width
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(stroke, paint);
  }

  void _paintApple(Canvas canvas, _SnakeHuntPath path, double progress) {
    if (!appleIsVisible(path.size, progress, motionSeed: motionSeed)) return;
    final appearing = progress >= _appleReturnsAt
        ? Curves.easeOutBack.transform(
            ((progress - _appleReturnsAt) / (1 - _appleReturnsAt)).clamp(
              0.0,
              1.0,
            ),
          )
        : 1.0;
    canvas.save();
    canvas.translate(path.apple.dx, path.apple.dy);
    canvas.scale(appearing, appearing);
    final fruitPaint = Paint()..color = warningColor;
    final outline = Paint()
      ..color = inkColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawCircle(Offset.zero, 11, fruitPaint);
    canvas.drawCircle(Offset.zero, 11, outline);
    canvas.drawLine(const Offset(0, -11), const Offset(3, -17), outline);
    canvas.drawOval(
      Rect.fromCenter(center: const Offset(7, -17), width: 9, height: 5),
      Paint()..color = leafColor,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant BlueRibbonPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.ribbonColor != ribbonColor ||
        oldDelegate.inkColor != inkColor ||
        oldDelegate.secondaryColor != secondaryColor ||
        oldDelegate.successColor != successColor ||
        oldDelegate.warningColor != warningColor ||
        oldDelegate.leafColor != leafColor ||
        oldDelegate.motionSeed != motionSeed;
  }
}

class _SnakeHuntPath {
  _SnakeHuntPath._(
    this.size,
    this.waypoints,
    this.points,
    this.cumulativeLengths,
    this.totalLength,
    this.applePointIndex,
  );

  static const _samplesPerSegment = 14;
  final Size size;
  final List<Offset> waypoints;
  final List<Offset> points;
  final List<double> cumulativeLengths;
  final double totalLength;
  final int applePointIndex;

  Offset get apple => waypoints[2];
  double get appleDistance => cumulativeLengths[applePointIndex];

  static _SnakeHuntPath generate(Size size, int seed) {
    final waypoints = _generateWaypoints(size, seed);
    final points = _smoothPoints(waypoints);
    final cumulativeLengths = <double>[0];
    for (var index = 0; index < points.length - 1; index++) {
      cumulativeLengths.add(
        cumulativeLengths.last + (points[index + 1] - points[index]).distance,
      );
    }
    return _SnakeHuntPath._(
      size,
      waypoints,
      points,
      cumulativeLengths,
      cumulativeLengths.last,
      2 * _samplesPerSegment,
    );
  }

  static List<Offset> _generateWaypoints(Size size, int seed) {
    final entrySide = (BlueRibbonPainter._noise(seed, 0, 1) * 4).floor();
    final exitSide = (entrySide + 2) % 4;
    final entry = _outsideEdge(
      size,
      entrySide,
      BlueRibbonPainter._lerp(0.18, 0.82, BlueRibbonPainter._noise(seed, 0, 2)),
    );
    final exit = _outsideEdge(
      size,
      exitSide,
      BlueRibbonPainter._lerp(0.18, 0.82, BlueRibbonPainter._noise(seed, 0, 3)),
    );
    final apple = Offset(
      size.width *
          BlueRibbonPainter._lerp(
            0.28,
            0.72,
            BlueRibbonPainter._noise(seed, 0, 4),
          ),
      size.height *
          BlueRibbonPainter._lerp(
            0.26,
            0.66,
            BlueRibbonPainter._noise(seed, 0, 5),
          ),
    );
    final bend =
        size.shortestSide *
        BlueRibbonPainter._lerp(
          0.13,
          0.24,
          BlueRibbonPainter._noise(seed, 0, 6),
        );
    final approachDirection = (apple - entry) / (apple - entry).distance;
    final normal = Offset(-approachDirection.dy, approachDirection.dx);
    final approach = Offset.lerp(entry, apple, 0.52)! + normal * bend;
    final departure = Offset.lerp(apple, exit, 0.48)! - normal * bend;
    return [entry, approach, apple, departure, exit];
  }

  static Offset _outsideEdge(Size size, int side, double along) {
    final bleed = size.shortestSide * 0.16;
    return switch (side) {
      0 => Offset(-bleed, size.height * along),
      1 => Offset(size.width * along, -bleed),
      2 => Offset(size.width + bleed, size.height * along),
      _ => Offset(size.width * along, size.height + bleed),
    };
  }

  static List<Offset> _smoothPoints(List<Offset> waypoints) {
    const tension = 0.24;
    final points = <Offset>[];
    for (var index = 0; index < waypoints.length - 1; index++) {
      final start = waypoints[index];
      final end = waypoints[index + 1];
      final before = index == 0 ? start * 2 - end : waypoints[index - 1];
      final after = index + 2 == waypoints.length
          ? end * 2 - start
          : waypoints[index + 2];
      for (var sample = 0; sample < _samplesPerSegment; sample++) {
        points.add(
          _catmullRom(
            before,
            start,
            end,
            after,
            sample / _samplesPerSegment,
            tension,
          ),
        );
      }
    }
    points.add(waypoints.last);
    return points;
  }

  static Offset _catmullRom(
    Offset before,
    Offset start,
    Offset end,
    Offset after,
    double t,
    double tension,
  ) {
    final t2 = t * t;
    final t3 = t2 * t;
    final tangentScale = (1 - tension) / 2;
    final startTangent = (end - before) * tangentScale;
    final endTangent = (after - start) * tangentScale;
    return start * (2 * t3 - 3 * t2 + 1) +
        startTangent * (t3 - 2 * t2 + t) +
        end * (-2 * t3 + 3 * t2) +
        endTangent * (t3 - t2);
  }

  _PathSample sampleAt(double distance) {
    final clamped = distance.clamp(0.0, totalLength);
    for (var index = 0; index < points.length - 1; index++) {
      final startDistance = cumulativeLengths[index];
      final endDistance = cumulativeLengths[index + 1];
      if (clamped > endDistance && index != points.length - 2) continue;
      final t = ((clamped - startDistance) / (endDistance - startDistance))
          .clamp(0.0, 1.0);
      return _PathSample(Offset.lerp(points[index], points[index + 1], t)!);
    }
    return _PathSample(points.last);
  }

  Path slice(double startDistance, double endDistance) {
    final start = startDistance.clamp(0.0, totalLength);
    final end = endDistance.clamp(0.0, totalLength);
    if (end <= start) return Path();
    final path = Path();
    var moved = false;
    for (var index = 0; index < points.length - 1; index++) {
      final segmentStart = cumulativeLengths[index];
      final segmentEnd = cumulativeLengths[index + 1];
      if (segmentEnd <= start || segmentStart >= end) continue;
      final clippedStart = start > segmentStart ? start : segmentStart;
      final clippedEnd = end < segmentEnd ? end : segmentEnd;
      final from = sampleAt(clippedStart).position;
      final to = sampleAt(clippedEnd).position;
      if (!moved) {
        path.moveTo(from.dx, from.dy);
        moved = true;
      }
      path.lineTo(to.dx, to.dy);
    }
    return path;
  }
}

class _PathSample {
  const _PathSample(this.position);

  final Offset position;
}
