import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class BalanceScreenMotion extends StatefulWidget {
  const BalanceScreenMotion({
    required this.child,
    this.seed = 0,
    this.offsetY = 12,
    super.key,
  });

  final Widget child;
  final int seed;
  final double offsetY;

  @override
  State<BalanceScreenMotion> createState() => _BalanceScreenMotionState();
}

class _BalanceScreenMotionState extends State<BalanceScreenMotion>
    with SingleTickerProviderStateMixin {
  static const _duration = Duration(milliseconds: 1100);
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: _duration,
  );
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    _play();
  }

  @override
  void didUpdateWidget(covariant BalanceScreenMotion oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.seed != widget.seed) {
      _play();
    }
  }

  void _play() {
    final disableAnimations =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    // TickerMode(false) thường được dùng khi tab bị ẩn hoặc khi chụp golden.
    // Nếu vẫn gọi forward, controller đứng ở 0 và cả màn hình trong suốt.
    if (disableAnimations || !TickerMode.valuesOf(context).enabled) {
      _controller.value = 1;
      return;
    }
    _controller.forward(from: 0);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    return AnimatedBuilder(
      animation: _controller,
      child: widget.child,
      builder: (context, child) {
        final t = Curves.easeOutCubic.transform(
          _controller.value.clamp(0.0, 1.0),
        );
        return Stack(
          fit: StackFit.passthrough,
          children: [
            _BalanceMotionScope(
              animation: _controller,
              child: child ?? const SizedBox.shrink(),
            ),
            Positioned.fill(
              child: IgnorePointer(
                child: CustomPaint(
                  painter: _BalanceSweepPainter(
                    progress: t,
                    bandColor: palette.primaryDark,
                    glowColor: palette.secondary,
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }
}

class BalanceReveal extends StatelessWidget {
  const BalanceReveal({
    required this.child,
    this.index = 0,
    this.start = 0.08,
    this.stagger = 0.075,
    this.span = 0.38,
    this.offsetY = 18,
    this.pop = true,
    super.key,
  });

  final Widget child;
  final int index;
  final double start;
  final double stagger;
  final double span;
  final double offsetY;
  final bool pop;

  @override
  Widget build(BuildContext context) {
    final animation = _BalanceMotionScope.maybeOf(context);
    if (animation == null) return child;
    return AnimatedBuilder(
      animation: animation,
      child: child,
      builder: (context, child) {
        final begin = (start + index * stagger).clamp(0.0, 0.92);
        final end = (begin + span).clamp(begin + 0.01, 1.0);
        final interval = Interval(begin, end, curve: Curves.easeOutCubic);
        final value = interval.transform(animation.value.clamp(0.0, 1.0));
        final scale = pop ? 0.965 + value * 0.035 : 1.0;
        return Opacity(
          opacity: value,
          // Điều khiển vẫn phải được screen reader nhận ra trong vài trăm ms
          // đầu của entrance motion.
          alwaysIncludeSemantics: true,
          child: Transform.translate(
            offset: Offset(0, (1 - value) * offsetY),
            child: Transform.scale(
              scale: scale,
              alignment: Alignment.topCenter,
              child: child,
            ),
          ),
        );
      },
    );
  }
}

class _BalanceMotionScope extends InheritedWidget {
  const _BalanceMotionScope({required this.animation, required super.child});

  final Animation<double> animation;

  static Animation<double>? maybeOf(BuildContext context) {
    return context
        .dependOnInheritedWidgetOfExactType<_BalanceMotionScope>()
        ?.animation;
  }

  @override
  bool updateShouldNotify(covariant _BalanceMotionScope oldWidget) {
    return oldWidget.animation != animation;
  }
}

class _BalanceSweepPainter extends CustomPainter {
  const _BalanceSweepPainter({
    required this.progress,
    this.bandColor = BalanceColors.blueDark,
    this.glowColor = BalanceColors.yellow,
  });

  final double progress;
  final Color bandColor;
  final Color glowColor;

  @override
  void paint(Canvas canvas, Size size) {
    if (progress <= 0) return;
    final eased = Curves.easeOutCubic.transform(progress);
    final travel = size.width + size.height * 1.25;
    final center = Offset(
      -size.width * 0.28 + travel * eased,
      size.height * 0.16 - travel * eased * 0.16,
    );

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(-0.33);

    final bandLength = size.longestSide * 1.85;
    final bandThickness = (size.shortestSide * 0.14).clamp(54.0, 112.0);
    final bandRect = Rect.fromCenter(
      center: Offset.zero,
      width: bandLength,
      height: bandThickness,
    );

    final bandPaint = Paint()..color = bandColor.withValues(alpha: 0.13);
    canvas.drawRRect(
      RRect.fromRectAndRadius(bandRect, Radius.circular(bandThickness / 2)),
      bandPaint,
    );

    final glowRect = Rect.fromCenter(
      center: const Offset(-42, 0),
      width: bandLength * 0.38,
      height: bandThickness * 0.36,
    );
    final glowPaint = Paint()..color = glowColor.withValues(alpha: 0.18);
    canvas.drawRRect(
      RRect.fromRectAndRadius(glowRect, Radius.circular(bandThickness * 0.18)),
      glowPaint,
    );

    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _BalanceSweepPainter oldDelegate) {
    return oldDelegate.progress != progress ||
        oldDelegate.bandColor != bandColor ||
        oldDelegate.glowColor != glowColor;
  }
}
