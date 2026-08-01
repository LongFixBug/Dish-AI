import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/features/analyze/data/analyze_api.dart';
import 'package:balance/features/analyze/data/sticker_api.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/domain/capture_stage.dart';
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
  CaptureStage _stage = CaptureStage.ready;

  /// Khoá chống bấm hai lần ngay khi chờ native picker mở ảnh.
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

  Future<void> _pickImage(ImageSource source) async {
    // Khoá NGAY, trước khi await picker. Nếu chỉ khoá sau đó, hai lần bấm nhanh
    // sẽ chạy hai lượt phân tích song song = hai lần gọi Vision tính phí.
    if (_busy || _stage.isAnalyzing) return;
    _busy = true;
    try {
      final image = await widget.pickImage(source);
      if (image == null || !mounted) return;
      final bytes = await image.readAsBytes();
      if (!mounted) return;
      setState(() {
        _imageBytes = bytes;
        _error = null;
        _stage = CaptureStage.review;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Không thể mở ảnh. Hãy thử lại nhé.';
        _stage = CaptureStage.ready;
      });
      debugPrint('Could not choose image: $error');
    } finally {
      _busy = false;
    }
  }

  Future<void> _analyzeSelectedImage() async {
    final bytes = _imageBytes;
    if (bytes == null || _stage.isAnalyzing) return;
    final filename = 'food-photo.jpg';
    setState(() {
      _error = null;
      _stage = CaptureStage.analyzing;
    });

    try {
      final analyze = widget.analyzeImage ?? _api!.analyzeImage;
      // Hai việc chạy song song: người dùng chỉ chờ bằng việc lâu hơn, chứ
      // không phải chờ cộng dồn cả hai.
      final analysis = analyze(bytes: bytes, filename: filename);
      final sticker = _cutOutSticker(bytes, filename);
      final result = await analysis;
      final stickerBytes = await sticker;
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        BalancePageRoute<void>(
          builder: (_) => AnalysisResultScreen(
            result: result,
            imageBytes: bytes,
            stickerBytes: stickerBytes,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error =
            'Chưa kết nối được để phân tích ảnh. Kiểm tra mạng rồi thử lại.';
        _stage = CaptureStage.review;
      });
      debugPrint('Could not analyze image: $error');
    } finally {
      if (mounted && _stage.isAnalyzing) {
        setState(() => _stage = CaptureStage.review);
      }
    }
  }

  void _retakePhoto() {
    setState(() {
      _imageBytes = null;
      _error = null;
      _stage = CaptureStage.ready;
    });
    _pickImage(ImageSource.camera);
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
    return BalanceScreenMotion(
      child: Scaffold(
        backgroundColor: BalanceColors.paperBlue,
        appBar: BalanceAppBar(
          title: 'Chụp món ăn',
          subtitle: 'Chọn ảnh rõ món ăn để Balance phân tích',
          actions: [
            Padding(
              padding: const EdgeInsets.only(right: 12),
              child: BalanceIconButton(
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
            child: LayoutBuilder(
              builder: (context, constraints) {
                final previewHeight = (constraints.maxHeight * 0.48).clamp(
                  250.0,
                  420.0,
                );
                return ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 18),
                  children: [
                    Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 520),
                        child: Column(
                          children: [
                            BalanceReveal(
                              index: 0,
                              child: SizedBox(
                                height: previewHeight,
                                child: AnalyzeCameraPreview(
                                  imageBytes: _imageBytes,
                                  stage: _stage,
                                ),
                              ),
                            ),
                            const SizedBox(height: 12),
                            BalanceReveal(
                              index: 2,
                              child: AnalyzeCaptureControls(
                                stage: _stage,
                                pickingImage: _busy,
                                error: _error,
                                onCamera: () => _pickImage(ImageSource.camera),
                                onGallery: () =>
                                    _pickImage(ImageSource.gallery),
                                onRetake: _retakePhoto,
                                onUsePhoto: _analyzeSelectedImage,
                                onTips: _showCaptureTips,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}
