import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

/// Luồng sáng quét dọc tấm ảnh trong lúc chờ phân tích.
///
/// Ngoài việc nhìn vui, nó còn làm một việc thật: nói cho người dùng biết máy
/// đang *làm gì đó* trên chính tấm ảnh của họ, thay vì một vòng xoay vô hồn.
class ScanBeam extends StatefulWidget {
  const ScanBeam({
    required this.imageBytes,
    this.running = true,
    this.borderRadius = 16,
    this.fallback,
    super.key,
  });

  final Uint8List imageBytes;
  final bool running;
  final double borderRadius;

  /// Hiện thay ảnh khi bytes không giải mã được (ảnh hỏng, hoặc dữ liệu giả
  /// trong test) — thiếu nó thì cả màn hình văng lỗi codec.
  final Widget? fallback;

  @override
  State<ScanBeam> createState() => _ScanBeamState();
}

class _ScanBeamState extends State<ScanBeam>
    with SingleTickerProviderStateMixin {
  // Tạo ngay trong initState, KHÔNG dùng `late final` khởi tạo lười: khi
  // widget dựng với running=false rồi bị huỷ, dòng dispose() sẽ là chỗ đầu
  // tiên chạm vào controller, và ticker đi tra ancestor trên một element đã
  // chết → "Looking up a deactivated widget's ancestor is unsafe".
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    );
    if (widget.running) _controller.repeat();
  }

  @override
  void didUpdateWidget(ScanBeam oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.running == oldWidget.running) return;
    if (widget.running) {
      _controller.repeat();
    } else {
      _controller.stop();
    }
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
      child: Stack(
        fit: StackFit.passthrough,
        children: [
          Image.memory(
            widget.imageBytes,
            fit: BoxFit.cover,
            errorBuilder: (_, _, _) =>
                widget.fallback ?? const ColoredBox(color: Color(0xFFCAD9E7)),
          ),
          if (widget.running)
            Positioned.fill(
              child: AnimatedBuilder(
                animation: _controller,
                builder: (context, _) => CustomPaint(
                  painter: _BeamPainter(progress: _controller.value),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _BeamPainter extends CustomPainter {
  const _BeamPainter({required this.progress});

  /// 0 → 1: vị trí tâm luồng sáng, tính từ mép trên xuống mép dưới.
  final double progress;

  static const _bandHeight = 0.22;

  @override
  void paint(Canvas canvas, Size size) {
    // Phủ một lớp tối rất nhẹ để dải sáng nổi lên, giống đèn quét trong tối.
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = Colors.black.withValues(alpha: 0.16),
    );

    final center = size.height * progress;
    final band = size.height * _bandHeight;
    final rect = Rect.fromLTRB(0, center - band, size.width, center + band);
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0x00449BFF),
            Color(0x66449BFF),
            Color(0xCCFFFFFF),
            Color(0x66449BFF),
            Color(0x00449BFF),
          ],
          stops: [0.0, 0.38, 0.5, 0.62, 1.0],
        ).createShader(rect),
    );

    // Vạch sáng mảnh ngay tâm dải, cho cảm giác "tia" chứ không phải "vệt mờ".
    canvas.drawLine(
      Offset(0, center),
      Offset(size.width, center),
      Paint()
        ..color = BalanceColors.blue
        ..strokeWidth = 2.5,
    );
  }

  @override
  bool shouldRepaint(_BeamPainter oldDelegate) =>
      oldDelegate.progress != progress;
}
