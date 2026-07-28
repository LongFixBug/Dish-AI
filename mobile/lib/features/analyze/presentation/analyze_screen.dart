import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/features/analyze/data/analyze_api.dart';
import 'package:balance/features/analyze/data/sticker_api.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analyze_capture_view.dart';
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

  void _showCaptureTips() {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('Chụp từ trên xuống, đủ sáng và lấy trọn phần ăn.'),
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: BalanceColors.paperBlue,
      appBar: AppBar(
        toolbarHeight: 72,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        title: const Column(
          children: [
            Text('Chụp món ăn'),
            Text(
              'AI nhận diện & tạo sticker',
              style: TextStyle(
                color: BalanceColors.muted,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
        leadingWidth: 68,
        leading: Padding(
          padding: const EdgeInsets.only(left: 12),
          child: CaptureIconButton(
            tooltip: 'Quay lại',
            icon: Icons.chevron_left_rounded,
            onPressed: () => Navigator.of(context).pop(),
          ),
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: CaptureIconButton(
              tooltip: 'Mẹo chụp',
              icon: Icons.info_outline_rounded,
              onPressed: _showCaptureTips,
            ),
          ),
        ],
      ),
      body: GraphPaperBackground(
        child: SafeArea(
          top: false,
          child: Column(
            children: [
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
                  child: AnalyzeCameraPreview(
                    imageBytes: _imageBytes,
                    loading: _loading,
                  ),
                ),
              ),
              AnalyzeCaptureControls(
                loading: _loading,
                error: _error,
                onCamera: () => _pickAndAnalyze(ImageSource.camera),
                onGallery: () => _pickAndAnalyze(ImageSource.gallery),
                onTips: _showCaptureTips,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
