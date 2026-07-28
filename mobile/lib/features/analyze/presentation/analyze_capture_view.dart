import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/features/analyze/presentation/scan_beam.dart';
import 'package:flutter/material.dart';

class AnalyzeCameraPreview extends StatelessWidget {
  const AnalyzeCameraPreview({
    required this.imageBytes,
    required this.loading,
    super.key,
  });

  final Uint8List? imageBytes;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      label: loading ? 'Ảnh món ăn đang được nhận diện' : 'Vùng quét món ăn',
      child: Container(
        key: const ValueKey('camera-preview-frame'),
        decoration: BoxDecoration(
          color: BalanceColors.ink,
          border: Border.all(color: BalanceColors.ink, width: 2.5),
          borderRadius: BorderRadius.circular(26),
          boxShadow: const [
            BoxShadow(color: BalanceColors.ink, offset: Offset(5, 7)),
          ],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(23),
          child: Stack(
            key: const ValueKey('camera-preview'),
            fit: StackFit.expand,
            children: [
              const _PreviewBackdrop(),
              _PreviewImage(imageBytes: imageBytes, loading: loading),
              const _PreviewVignette(),
              const _FocusCorners(),
              Positioned(
                top: 18,
                left: 18,
                child: _ScanStatus(loading: loading),
              ),
              Positioned(
                left: 18,
                right: 18,
                bottom: 18,
                child: _CameraGuidance(loading: loading),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PreviewBackdrop extends StatelessWidget {
  const _PreviewBackdrop();

  @override
  Widget build(BuildContext context) {
    return const DecoratedBox(
      decoration: BoxDecoration(
        gradient: RadialGradient(
          center: Alignment(0, -0.2),
          radius: 1.05,
          colors: [Color(0x33FFFFFF), Color(0x006B9FDB)],
        ),
      ),
    );
  }
}

class _PreviewImage extends StatelessWidget {
  const _PreviewImage({required this.imageBytes, required this.loading});

  final Uint8List? imageBytes;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    if (imageBytes case final bytes?) {
      return LayoutBuilder(
        builder: (context, constraints) => Center(
          child: SizedBox(
            key: const ValueKey('gallery-photo-preview'),
            width: constraints.maxWidth * 0.78,
            height: constraints.maxHeight * 0.58,
            child: ScanBeam(
              imageBytes: bytes,
              running: loading,
              borderRadius: 28,
              fit: BoxFit.contain,
              fallback: const FoodPhoto(
                meal: FoodPhotoMeal.comTam,
                fit: BoxFit.contain,
              ),
            ),
          ),
        ),
      );
    }
    return const Center(child: _EmptyPlate());
  }
}

class _EmptyPlate extends StatelessWidget {
  const _EmptyPlate();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 126,
      height: 126,
      decoration: BoxDecoration(
        color: BalanceColors.paper.withValues(alpha: 0.94),
        shape: BoxShape.circle,
        border: Border.all(color: BalanceColors.ink, width: 2.5),
        boxShadow: const [
          BoxShadow(color: BalanceColors.ink, offset: Offset(5, 6)),
        ],
      ),
      child: const Icon(
        Icons.ramen_dining_rounded,
        color: BalanceColors.blueDark,
        size: 62,
      ),
    );
  }
}

class _PreviewVignette extends StatelessWidget {
  const _PreviewVignette();

  @override
  Widget build(BuildContext context) {
    return const IgnorePointer(
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0x33000000),
              Color(0x00000000),
              Color(0x00000000),
              Color(0x55000000),
            ],
            stops: [0, 0.24, 0.62, 1],
          ),
        ),
      ),
    );
  }
}

class _ScanStatus extends StatelessWidget {
  const _ScanStatus({required this.loading});

  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: loading ? BalanceColors.yellow : BalanceColors.paper,
        border: Border.all(color: BalanceColors.ink, width: 2),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 9,
            height: 9,
            decoration: BoxDecoration(
              color: loading ? BalanceColors.orange : BalanceColors.green,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 7),
          Text(
            loading ? 'AI ĐANG QUÉT' : 'SẴN SÀNG',
            style: const TextStyle(
              color: BalanceColors.ink,
              fontSize: 12,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.5,
            ),
          ),
        ],
      ),
    );
  }
}

class _CameraGuidance extends StatelessWidget {
  const _CameraGuidance({required this.loading});

  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: BalanceColors.paper.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (loading) ...[
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    color: BalanceColors.blueDark,
                    strokeWidth: 2.4,
                  ),
                ),
                const SizedBox(width: 9),
              ],
              Flexible(
                child: Text(
                  loading ? 'Đang quét món ăn' : 'Đặt món ở giữa vùng quét',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: BalanceColors.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Text(
            loading
                ? 'Vạch quét cong khi chạm tới món ăn'
                : 'Chụp rõ món ăn • nơi đủ sáng',
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: BalanceColors.muted,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }
}

class AnalyzeCaptureControls extends StatelessWidget {
  const AnalyzeCaptureControls({
    required this.loading,
    required this.error,
    required this.onCamera,
    required this.onGallery,
    required this.onTips,
    super.key,
  });

  final bool loading;
  final String? error;
  final VoidCallback onCamera;
  final VoidCallback onGallery;
  final VoidCallback onTips;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 16),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (error case final message?) ...[
            _CaptureError(message: message, onRetry: onGallery),
            const SizedBox(height: 10),
          ],
          Container(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
            decoration: BoxDecoration(
              color: BalanceColors.paper,
              border: Border.all(color: BalanceColors.ink, width: 2.5),
              borderRadius: BorderRadius.circular(22),
              boxShadow: const [
                BoxShadow(color: BalanceColors.ink, offset: Offset(4, 5)),
              ],
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Expanded(
                  child: _ControlAction(
                    key: const ValueKey('gallery-action'),
                    icon: Icons.photo_library_rounded,
                    label: 'Thư viện',
                    onPressed: loading ? null : onGallery,
                  ),
                ),
                const SizedBox(width: 8),
                _ShutterButton(loading: loading, onPressed: onCamera),
                const SizedBox(width: 8),
                Expanded(
                  child: _ControlAction(
                    key: const ValueKey('tips-action'),
                    icon: Icons.auto_awesome_rounded,
                    label: 'Mẹo chụp',
                    onPressed: loading ? null : onTips,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ControlAction extends StatelessWidget {
  const _ControlAction({
    required this.icon,
    required this.label,
    required this.onPressed,
    super.key,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Semantics(
      button: true,
      enabled: enabled,
      label: label,
      child: InkWell(
        onTap: onPressed,
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 48,
                height: 44,
                decoration: BoxDecoration(
                  color: enabled
                      ? BalanceColors.paperBlue
                      : BalanceColors.paperBlue.withValues(alpha: 0.45),
                  border: Border.all(
                    color: BalanceColors.ink.withValues(
                      alpha: enabled ? 1 : 0.35,
                    ),
                    width: 2,
                  ),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  icon,
                  color: enabled ? BalanceColors.ink : BalanceColors.muted,
                  size: 24,
                ),
              ),
              const SizedBox(height: 5),
              Text(
                label,
                maxLines: 1,
                style: TextStyle(
                  color: enabled ? BalanceColors.ink : BalanceColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ShutterButton extends StatelessWidget {
  const _ShutterButton({required this.loading, required this.onPressed});

  final bool loading;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      enabled: !loading,
      label: 'Chụp ảnh',
      child: GestureDetector(
        key: const ValueKey('camera-shutter'),
        onTap: loading ? null : onPressed,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              width: 76,
              height: 76,
              padding: const EdgeInsets.all(7),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: BalanceColors.paper,
                border: Border.all(color: BalanceColors.ink, width: 2.8),
              ),
              child: DecoratedBox(
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: loading ? BalanceColors.muted : BalanceColors.blue,
                ),
                child: loading
                    ? const Padding(
                        padding: EdgeInsets.all(16),
                        child: CircularProgressIndicator(
                          color: Colors.white,
                          strokeWidth: 3,
                        ),
                      )
                    : null,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              loading ? 'Đang xử lý' : 'Chụp ảnh',
              style: const TextStyle(
                color: BalanceColors.ink,
                fontSize: 12,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CaptureError extends StatelessWidget {
  const _CaptureError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 9, 8, 9),
      decoration: BoxDecoration(
        color: const Color(0xFFFFE7DE),
        border: Border.all(color: BalanceColors.ink, width: 2),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded, size: 22),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Chưa phân tích được ảnh',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(message, maxLines: 1, overflow: TextOverflow.ellipsis),
              ],
            ),
          ),
          TextButton(onPressed: onRetry, child: const Text('Thử lại')),
        ],
      ),
    );
  }
}

class CaptureIconButton extends StatelessWidget {
  const CaptureIconButton({
    required this.icon,
    required this.tooltip,
    this.onPressed,
    super.key,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      icon: Icon(icon),
      style: IconButton.styleFrom(
        minimumSize: const Size(46, 46),
        backgroundColor: BalanceColors.paper,
        foregroundColor: BalanceColors.ink,
        side: const BorderSide(color: BalanceColors.ink, width: 2),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(13)),
      ),
    );
  }
}

class _FocusCorners extends StatelessWidget {
  const _FocusCorners();

  @override
  Widget build(BuildContext context) {
    return const IgnorePointer(
      key: ValueKey('capture-focus-corners'),
      child: Padding(
        padding: EdgeInsets.all(26),
        child: CustomPaint(painter: _CornerPainter()),
      ),
    );
  }
}

class _CornerPainter extends CustomPainter {
  const _CornerPainter();

  @override
  void paint(Canvas canvas, Size size) {
    const length = 36.0;
    final paint = Paint()
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    final paths = [
      Path()
        ..moveTo(0, length)
        ..lineTo(0, 0)
        ..lineTo(length, 0),
      Path()
        ..moveTo(size.width - length, 0)
        ..lineTo(size.width, 0)
        ..lineTo(size.width, length),
      Path()
        ..moveTo(0, size.height - length)
        ..lineTo(0, size.height)
        ..lineTo(length, size.height),
      Path()
        ..moveTo(size.width - length, size.height)
        ..lineTo(size.width, size.height)
        ..lineTo(size.width, size.height - length),
    ];
    for (final path in paths) {
      canvas.drawPath(
        path,
        paint
          ..color = BalanceColors.ink
          ..strokeWidth = 5,
      );
      canvas.drawPath(
        path,
        paint
          ..color = Colors.white
          ..strokeWidth = 2.5,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
