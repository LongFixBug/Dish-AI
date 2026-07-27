import 'dart:math';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/mascot/domain/mascot_pose.dart';
import 'package:balance/features/mascot/domain/mascot_shape.dart';
import 'package:balance/features/mascot/presentation/mascot_painter.dart';
import 'package:flutter/material.dart';

/// Linh vật Balance đi qua đi lại trong một dải ngang.
///
/// Widget này chỉ làm đúng hai việc: đếm nhịp thời gian và đặt nhân vật vào
/// đúng chỗ trên dải. Dáng đi nằm trong [mascotPoseAt], hình hài nằm trong
/// [MascotPainter] — chia ba như vậy để sửa nhịp bước không phải đụng tới nét
/// vẽ, và ngược lại.
class WalkingMascot extends StatefulWidget {
  const WalkingMascot({
    required this.shape,
    this.height = 100,
    this.animate = true,
    this.showCaption = true,
    super.key,
  });

  final MascotShape shape;
  final double height;

  /// Tắt trong test/golden để khung hình đầu đã đứng yên.
  final bool animate;
  final bool showCaption;

  @override
  State<WalkingMascot> createState() => _WalkingMascotState();
}

class _WalkingMascotState extends State<WalkingMascot>
    with SingleTickerProviderStateMixin {
  // Khởi tạo trong initState, không dùng `late final` lười: widget dựng rồi bị
  // huỷ trước khi chạm tới sẽ khiến dispose() là nơi đầu tiên tạo controller,
  // và ticker đi tra ancestor trên element đã chết.
  late final AnimationController _controller;

  /// Một vòng = đi hết sang phải, quay đầu, đi ngược về, quay lại như cũ.
  static const _lapDuration = Duration(seconds: 11);

  /// Đi vài vòng rồi nghỉ, KHÔNG lặp vô hạn.
  ///
  /// Hai lý do: chạy mãi thì ngốn pin dù người dùng đã cuộn đi chỗ khác, và
  /// animation không bao giờ dừng khiến `pumpAndSettle` trong widget test treo
  /// vĩnh viễn — mọi test chạm tới trang chủ sẽ chết theo.
  static const _laps = 3;

  /// Chừa chỗ cho cái đuôi thò ra ngoài rìa hộp vẽ.
  static const _captionHeight = 22.0;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: _lapDuration);
    if (widget.animate) {
      _controller.repeat(count: _laps);
    } else {
      _controller.value = kMascotRestPhase;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: widget.height + (widget.showCaption ? _captionHeight : 0),
      child: Column(
        children: [
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final size = min(widget.height, constraints.maxHeight);
                final lane = (constraints.maxWidth - size).clamp(0.0, 4000.0);
                return AnimatedBuilder(
                  animation: _controller,
                  builder: (context, _) {
                    final pose = mascotPoseAt(_controller.value);
                    return Stack(
                      children: [
                        Positioned(
                          left: lane * pose.travel,
                          bottom: 0,
                          width: size,
                          height: size,
                          child: CustomPaint(
                            painter: MascotPainter(
                              pose: pose,
                              shape: widget.shape,
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                );
              },
            ),
          ),
          if (widget.showCaption)
            SizedBox(
              height: _captionHeight,
              child: Text(
                mascotCaptionFor(widget.shape),
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                  color: BalanceColors.muted,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
