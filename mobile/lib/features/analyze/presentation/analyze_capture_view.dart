import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_notice.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/domain/capture_stage.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/features/analyze/presentation/scan_beam.dart';
import 'package:flutter/material.dart';

class AnalyzeCameraPreview extends StatelessWidget {
  const AnalyzeCameraPreview({
    required this.imageBytes,
    required this.stage,
    super.key,
  });

  final Uint8List? imageBytes;
  final CaptureStage stage;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      image: true,
      label: stage.isAnalyzing
          ? 'Ảnh món ăn đang được nhận diện'
          : 'Vùng chọn ảnh món ăn',
      child: Container(
        key: const ValueKey('camera-preview-frame'),
        decoration: BoxDecoration(
          color: BalanceColors.ink,
          border: Border.all(
            color: BalanceColors.ink.withValues(alpha: 0.86),
            width: BalanceStrokes.strong,
          ),
          borderRadius: BorderRadius.circular(BalanceRadii.sheet),
          boxShadow: const [BalanceShadows.floating],
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(BalanceRadii.sheet - 3),
          child: Stack(
            key: const ValueKey('camera-preview'),
            fit: StackFit.expand,
            children: [
              const _PreviewBackdrop(),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 220),
                child: _PreviewImage(
                  key: ValueKey('preview-${stage.name}-${imageBytes != null}'),
                  imageBytes: imageBytes,
                  stage: stage,
                ),
              ),
              const _FocusCorners(),
              Positioned(top: 18, left: 18, child: _ScanStatus(stage: stage)),
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
      decoration: BoxDecoration(color: Color(0xFF243142)),
    );
  }
}

class _PreviewImage extends StatelessWidget {
  const _PreviewImage({
    required this.imageBytes,
    required this.stage,
    super.key,
  });

  final Uint8List? imageBytes;
  final CaptureStage stage;

  @override
  Widget build(BuildContext context) {
    if (imageBytes case final bytes?) {
      return LayoutBuilder(
        builder: (context, constraints) => Center(
          child: SizedBox(
            key: const ValueKey('gallery-photo-preview'),
            width: constraints.maxWidth * 0.74,
            height: constraints.maxHeight * 0.54,
            child: ScanBeam(
              imageBytes: bytes,
              running: stage.isAnalyzing,
              borderRadius: 18,
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
      key: const ValueKey('capture-empty-state'),
      width: 116,
      height: 116,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: BalanceColors.paper,
        shape: BoxShape.circle,
        border: Border.all(
          color: BalanceColors.ink.withValues(alpha: 0.82),
          width: BalanceStrokes.strong,
        ),
        boxShadow: const [BalanceShadows.floating],
      ),
      child: const Icon(
        Icons.ramen_dining_rounded,
        color: BalanceColors.blueDark,
        size: 58,
      ),
    );
  }
}

class _ScanStatus extends StatelessWidget {
  const _ScanStatus({required this.stage});

  final CaptureStage stage;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: stage.isAnalyzing ? BalanceColors.yellow : BalanceColors.paper,
        border: Border.all(
          color: BalanceColors.ink.withValues(alpha: 0.6),
          width: BalanceStrokes.regular,
        ),
        borderRadius: BorderRadius.circular(BalanceRadii.pill),
        boxShadow: const [BalanceShadows.card],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 9,
            height: 9,
            decoration: BoxDecoration(
              color: stage.isAnalyzing
                  ? BalanceColors.orange
                  : BalanceColors.green,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 7),
          Text(
            switch (stage) {
              CaptureStage.ready => 'CHỌN ẢNH',
              CaptureStage.review => 'SẴN SÀNG',
              CaptureStage.analyzing => 'AI ĐANG QUÉT',
            },
            style: const TextStyle(
              color: BalanceColors.ink,
              fontSize: 11.5,
              fontWeight: FontWeight.w900,
              letterSpacing: 0.4,
            ),
          ),
        ],
      ),
    );
  }
}

class AnalyzeCaptureControls extends StatelessWidget {
  const AnalyzeCaptureControls({
    required this.stage,
    required this.pickingImage,
    required this.error,
    required this.onCamera,
    required this.onGallery,
    required this.onRetake,
    required this.onUsePhoto,
    required this.onTips,
    super.key,
  });

  final CaptureStage stage;
  final bool pickingImage;
  final String? error;
  final VoidCallback onCamera;
  final VoidCallback onGallery;
  final VoidCallback onRetake;
  final VoidCallback onUsePhoto;
  final VoidCallback onTips;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (error case final message?) ...[
          _CaptureError(message: message, onRetry: onGallery),
          const SizedBox(height: 10),
        ],
        SketchCard(
          key: const ValueKey('capture-action-sheet'),
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
          radius: BalanceRadii.card,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 180),
            switchInCurve: Curves.easeOutCubic,
            switchOutCurve: Curves.easeInCubic,
            child: switch (stage) {
              CaptureStage.review => _ReviewControls(
                key: const ValueKey('review-controls'),
                onRetake: onRetake,
                onUsePhoto: onUsePhoto,
              ),
              CaptureStage.analyzing => const _AnalyzingControls(
                key: ValueKey('analyzing-controls'),
              ),
              CaptureStage.ready => _PickControls(
                key: const ValueKey('pick-controls'),
                disabled: pickingImage,
                onCamera: onCamera,
                onGallery: onGallery,
                onTips: onTips,
              ),
            },
          ),
        ),
      ],
    );
  }
}

class _PickControls extends StatelessWidget {
  const _PickControls({
    required this.disabled,
    required this.onCamera,
    required this.onGallery,
    required this.onTips,
    super.key,
  });

  final bool disabled;
  final VoidCallback onCamera;
  final VoidCallback onGallery;
  final VoidCallback onTips;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _ActionHeader(
          icon: Icons.document_scanner_outlined,
          title: 'Bắt đầu quét món ăn',
          subtitle: 'Đưa món vào khung, chụp từ trên xuống, đủ sáng.',
        ),
        const SizedBox(height: 12),
        SizedBox(
          key: const ValueKey('camera-shutter'),
          child: PressableButton(
            onPressed: disabled ? null : onCamera,
            icon: Icons.camera_alt_rounded,
            label: 'Mở camera',
          ),
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _SecondaryCaptureAction(
                key: const ValueKey('gallery-action'),
                icon: Icons.photo_library_outlined,
                label: 'Thư viện',
                onPressed: disabled ? null : onGallery,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: _SecondaryCaptureAction(
                key: const ValueKey('tips-action'),
                icon: Icons.lightbulb_outline_rounded,
                label: 'Mẹo chụp',
                onPressed: disabled ? null : onTips,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _ActionHeader extends StatelessWidget {
  const _ActionHeader({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _SheetIcon(icon: icon),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: BalanceColors.ink,
                  fontSize: 17,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                subtitle,
                style: const TextStyle(
                  color: BalanceColors.muted,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SheetIcon extends StatelessWidget {
  const _SheetIcon({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 34,
      height: 34,
      decoration: BoxDecoration(
        color: BalanceColors.paperBlue,
        shape: BoxShape.circle,
        border: Border.all(
          color: BalanceColors.ink.withValues(alpha: 0.64),
          width: BalanceStrokes.regular,
        ),
        boxShadow: const [BalanceShadows.card],
      ),
      child: Icon(icon, color: BalanceColors.blueDark, size: 19),
    );
  }
}

class _SecondaryCaptureAction extends StatefulWidget {
  const _SecondaryCaptureAction({
    required this.icon,
    required this.label,
    required this.onPressed,
    super.key,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  State<_SecondaryCaptureAction> createState() =>
      _SecondaryCaptureActionState();
}

class _SecondaryCaptureActionState extends State<_SecondaryCaptureAction> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (widget.onPressed == null || _pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    return Semantics(
      button: true,
      enabled: enabled,
      label: widget.label,
      child: Listener(
        onPointerDown: enabled ? (_) => _setPressed(true) : null,
        onPointerUp: enabled ? (_) => _setPressed(false) : null,
        onPointerCancel: enabled ? (_) => _setPressed(false) : null,
        child: GestureDetector(
          onTap: widget.onPressed,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 140),
            curve: Curves.easeOutCubic,
            transform: Matrix4.translationValues(0, _pressed ? 3 : 0, 0),
            height: 44,
            padding: const EdgeInsets.symmetric(horizontal: 8),
            decoration: BoxDecoration(
              color: enabled ? BalanceColors.paperBlue : BalanceColors.paper,
              border: Border.all(
                color: BalanceColors.ink.withValues(alpha: 0.62),
                width: BalanceStrokes.regular,
              ),
              borderRadius: BorderRadius.circular(BalanceRadii.control),
              boxShadow: [
                BoxShadow(
                  color: BalanceColors.ink.withValues(
                    alpha: enabled ? 0.18 : 0.06,
                  ),
                  offset: _pressed ? const Offset(0, 1) : const Offset(0, 5),
                  blurRadius: _pressed ? 2 : 10,
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  widget.icon,
                  color: enabled ? BalanceColors.blueDark : BalanceColors.muted,
                  size: 19,
                ),
                const SizedBox(width: 6),
                Flexible(
                  child: Text(
                    widget.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: enabled ? BalanceColors.ink : BalanceColors.muted,
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ReviewControls extends StatelessWidget {
  const _ReviewControls({
    required this.onRetake,
    required this.onUsePhoto,
    super.key,
  });

  final VoidCallback onRetake;
  final VoidCallback onUsePhoto;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _ActionHeader(
          icon: Icons.check_circle_outline_rounded,
          title: 'Ảnh đã sẵn sàng',
          subtitle: 'Xác nhận để Balance bắt đầu phân tích.',
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: PressableButton(
                onPressed: onRetake,
                icon: Icons.camera_alt_outlined,
                label: 'Chụp lại',
                backgroundColor: BalanceColors.paperBlue,
                foregroundColor: BalanceColors.ink,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: PressableButton(
                onPressed: onUsePhoto,
                icon: Icons.auto_awesome_rounded,
                label: 'Dùng ảnh này',
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _AnalyzingControls extends StatelessWidget {
  const _AnalyzingControls({super.key});

  @override
  Widget build(BuildContext context) {
    return const Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _ActionHeader(
          icon: Icons.auto_awesome_motion_rounded,
          title: 'Balance đang đọc ảnh',
          subtitle: 'Đợi một lát để AI đối chiếu món và khẩu phần.',
        ),
        SizedBox(height: 14),
        Row(
          children: [
            SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(
                color: BalanceColors.blueDark,
                strokeWidth: 2.6,
              ),
            ),
            SizedBox(width: 10),
            Expanded(
              child: Text(
                'Đang phân tích ảnh món ăn...',
                style: TextStyle(
                  color: BalanceColors.muted,
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _CaptureError extends StatelessWidget {
  const _CaptureError({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return BalanceNotice(
      icon: Icons.error_outline_rounded,
      title: 'Chưa phân tích được ảnh',
      message: message,
      color: BalanceColors.dangerPaper,
      actionLabel: 'Thử lại',
      onAction: onRetry,
      shadow: true,
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
        padding: EdgeInsets.all(20),
        child: CustomPaint(painter: _CornerPainter()),
      ),
    );
  }
}

class _CornerPainter extends CustomPainter {
  const _CornerPainter();

  @override
  void paint(Canvas canvas, Size size) {
    const length = 28.0;
    final paint = Paint()
      ..strokeWidth = 4
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
          ..strokeWidth = 4,
      );
      canvas.drawPath(
        path,
        paint
          ..color = Colors.white
          ..strokeWidth = 2.2,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
