import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/data/analyze_api.dart';
import 'package:balance/features/analyze/data/sticker_api.dart';
import 'package:balance/features/analyze/presentation/scan_beam.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

typedef PickImage = Future<XFile?> Function(ImageSource source);
typedef AnalyzeImage =
    Future<AnalyzeResult> Function({
      required Uint8List bytes,
      required String filename,
    });

class AnalyzeScreen extends StatefulWidget {
  const AnalyzeScreen({
    this.pickImage = _devicePickImage,
    this.analyzeImage,
    this.stickerGateway,
    super.key,
  });

  final PickImage pickImage;
  final AnalyzeImage? analyzeImage;

  /// Bỏ trống thì dùng backend thật; test tiêm bản giả để khỏi chạm mạng.
  final StickerGateway? stickerGateway;

  static Future<XFile?> _devicePickImage(ImageSource source) {
    return ImagePicker().pickImage(
      source: source,
      imageQuality: 88,
      maxWidth: 1920,
    );
  }

  @override
  State<AnalyzeScreen> createState() => _AnalyzeScreenState();
}

class _AnalyzeScreenState extends State<AnalyzeScreen> {
  AnalyzeApi? _api;
  StickerApi? _stickerApi;
  Uint8List? _imageBytes;
  String? _error;
  bool _loading = false;

  /// Khoá chống bấm hai lần, bật ngay khi bắt đầu — kể cả trong lúc chờ picker,
  /// giai đoạn mà [_loading] còn false nên nút vẫn bấm được.
  bool _busy = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (widget.analyzeImage == null && _api == null) {
      final state = AppScope.maybeOf(context);
      _api = AnalyzeApi(accessTokenProvider: state?.validAccessToken);
    }
  }

  @override
  void dispose() {
    _stickerApi?.close();
    _api?.close();
    super.dispose();
  }

  /// Sticker là phần trang trí: hỏng thì trả null để màn kết quả dùng ảnh gốc.
  Future<Uint8List?> _cutOutSticker(Uint8List bytes, String filename) async {
    final state = AppScope.maybeOf(context);
    if (state == null) return null;
    final gateway = widget.stickerGateway ?? (_stickerApi ??= StickerApi());
    try {
      final token = await state.validAccessToken();
      return await gateway.cutOut(
        imageBytes: bytes,
        filename: filename,
        accessToken: token,
      );
    } on Object {
      return null;
    }
  }

  Future<void> _pickAndAnalyze(ImageSource source) async {
    // Khoá NGAY, trước khi await picker. Nếu chỉ khoá sau đó, hai lần bấm nhanh
    // sẽ chạy hai lượt phân tích song song = hai lần gọi Vision tính phí.
    if (_busy) return;
    _busy = true;
    try {
      final image = await widget.pickImage(source);
      if (image == null || !mounted) return;
      final bytes = await image.readAsBytes();
      if (!mounted) return;
      setState(() {
        _imageBytes = bytes;
        _error = null;
        _loading = true;
      });

      final analyze = widget.analyzeImage ?? _api!.analyzeImage;
      // Hai việc chạy song song: người dùng chỉ chờ bằng việc lâu hơn, chứ
      // không phải chờ cộng dồn cả hai.
      final analysis = analyze(bytes: bytes, filename: image.name);
      final sticker = _cutOutSticker(bytes, image.name);
      final result = await analysis;
      final stickerBytes = await sticker;
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => AnalysisResultScreen(
            result: result,
            imageBytes: bytes,
            stickerBytes: stickerBytes,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      _busy = false;
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BalanceColors.paperBlue,
      appBar: AppBar(
        title: const Text('Chụp món ăn'),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
        leading: _SquareIconButton(
          icon: Icons.chevron_left_rounded,
          onPressed: () => Navigator.of(context).pop(),
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: _SquareIconButton(
              icon: Icons.info_outline_rounded,
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text(
                    'Chụp rõ toàn bộ món ăn hoặc chọn ảnh từ thư viện.',
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        top: false,
        child: Column(
          children: [
            Expanded(
              child: _CameraFrame(imageBytes: _imageBytes, loading: _loading),
            ),
            _CaptureControls(
              loading: _loading,
              error: _error,
              onCamera: () => _pickAndAnalyze(ImageSource.camera),
              onGallery: () => _pickAndAnalyze(ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
  }
}

class _CaptureControls extends StatelessWidget {
  const _CaptureControls({
    required this.loading,
    required this.error,
    required this.onCamera,
    required this.onGallery,
  });

  final bool loading;
  final String? error;
  final VoidCallback onCamera;
  final VoidCallback onGallery;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(22, 18, 22, 16),
      child: Column(
        children: [
          if (error case final message?) ...[
            _CaptureError(message: message, onRetry: onGallery),
            const SizedBox(height: 12),
          ],
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _SquareIconButton(
                icon: Icons.photo_library_rounded,
                onPressed: loading ? null : onGallery,
              ),
              _ShutterButton(loading: loading, onPressed: onCamera),
              _SquareIconButton(
                icon: Icons.camera_alt_outlined,
                onPressed: loading ? null : onCamera,
              ),
            ],
          ),
          const SizedBox(height: 12),
          TextButton(
            onPressed: loading ? null : onGallery,
            child: const Text(
              'Chọn ảnh từ thư viện',
              style: TextStyle(
                decoration: TextDecoration.underline,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
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
    return SketchCard(
      color: const Color(0xFFFFE7DE),
      shadow: false,
      child: Row(
        children: [
          const Icon(Icons.error_outline_rounded),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Chưa phân tích được ảnh',
                  style: TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(message, maxLines: 2),
                TextButton(onPressed: onRetry, child: const Text('Thử lại')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _CameraFrame extends StatelessWidget {
  const _CameraFrame({required this.imageBytes, required this.loading});

  final Uint8List? imageBytes;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        if (imageBytes case final bytes?)
          // Đang phân tích thì luồng sáng quét dọc tấm ảnh, để người dùng
          // thấy máy đang làm việc trên đúng ảnh của mình.
          ScanBeam(
            imageBytes: bytes,
            running: loading,
            borderRadius: 0,
            fallback: const FoodPhoto(meal: FoodPhotoMeal.comTam),
          )
        else
          const ColoredBox(
            color: Color(0xFFCAD9E7),
            child: Center(
              child: Icon(
                Icons.restaurant_rounded,
                size: 94,
                color: Colors.white,
              ),
            ),
          ),
        const _FocusCorners(),
        Positioned(
          left: 0,
          right: 0,
          bottom: 18,
          child: Center(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: BalanceColors.paper,
                border: Border.all(color: BalanceColors.ink, width: 1.8),
                borderRadius: BorderRadius.circular(7),
              ),
              child: Text(
                loading
                    ? 'Balance đang xem món ăn...'
                    : 'Đặt món ăn vào giữa khung',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
            ),
          ),
        ),
        if (loading)
          const ColoredBox(
            color: Color(0x55000000),
            child: Center(
              child: CircularProgressIndicator(color: Colors.white),
            ),
          ),
      ],
    );
  }
}

class _FocusCorners extends StatelessWidget {
  const _FocusCorners();

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: Padding(
        padding: const EdgeInsets.all(26),
        child: CustomPaint(painter: _CornerPainter()),
      ),
    );
  }
}

class _CornerPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    const length = 38.0;
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
      canvas.drawPath(path, paint..color = BalanceColors.ink);
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

class _ShutterButton extends StatelessWidget {
  const _ShutterButton({required this.loading, required this.onPressed});

  final bool loading;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      key: const ValueKey('camera-shutter'),
      onTap: loading ? null : onPressed,
      child: Container(
        width: 82,
        height: 82,
        padding: const EdgeInsets.all(7),
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: BalanceColors.paper,
          border: Border.all(color: BalanceColors.ink, width: 2.5),
        ),
        child: const DecoratedBox(
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: BalanceColors.blue,
          ),
        ),
      ),
    );
  }
}

class _SquareIconButton extends StatelessWidget {
  const _SquareIconButton({required this.icon, this.onPressed});

  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onPressed,
      icon: Icon(icon),
      style: IconButton.styleFrom(
        backgroundColor: BalanceColors.paper,
        foregroundColor: BalanceColors.ink,
        side: const BorderSide(color: BalanceColors.ink, width: 2),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(7)),
      ),
    );
  }
}
