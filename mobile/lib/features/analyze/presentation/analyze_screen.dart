import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/sketch_card.dart';
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
typedef AnalyzeText =
    Future<AnalyzeResult> Function({
      required String foodName,
      required double grams,
    });

class AnalyzeScreen extends StatefulWidget {
  const AnalyzeScreen({
    this.pickImage = _devicePickImage,
    this.analyzeImage,
    this.analyzeText,
    this.stickerGateway,
    super.key,
  });

  final PickImage pickImage;
  final AnalyzeImage? analyzeImage;
  final AnalyzeText? analyzeText;

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
  String _captureSource = 'upload';
  String? _error;
  CaptureStage _stage = CaptureStage.ready;
  bool _textMode = false;
  List<AnalyzeMatch> _textMatches = const [];
  late final TextEditingController _foodNameController;
  late final TextEditingController _gramsController;

  /// Khoá chống bấm hai lần ngay khi chờ native picker mở ảnh.
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _foodNameController = TextEditingController();
    _gramsController = TextEditingController(text: '100');
  }

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
    _foodNameController.dispose();
    _gramsController.dispose();
    _stickerApi?.close();
    _api?.close();
    super.dispose();
  }

  void _setTextMode(bool value) {
    if (_busy || _stage.isAnalyzing || _textMode == value) return;
    setState(() {
      _textMode = value;
      _imageBytes = null;
      _captureSource = 'upload';
      _error = null;
      _textMatches = const [];
      _stage = CaptureStage.ready;
    });
  }

  Future<void> _analyzeTypedFood() async {
    if (_stage.isAnalyzing) return;
    final foodName = _foodNameController.text.trim().replaceAll(
      RegExp(r'\s+'),
      ' ',
    );
    final grams = double.tryParse(_gramsController.text.trim());
    if (foodName.isEmpty) {
      setState(() => _error = 'Hãy nhập tên món ăn.');
      return;
    }
    if (grams == null || !grams.isFinite || grams <= 0 || grams > 10000) {
      setState(() => _error = 'Khối lượng phải từ 1 đến 10.000 gram.');
      return;
    }
    setState(() {
      _error = null;
      _textMatches = const [];
      _stage = CaptureStage.analyzing;
    });
    try {
      final analyze = widget.analyzeText ?? _api!.analyzeText;
      final result = await analyze(foodName: foodName, grams: grams);
      if (!mounted) return;
      if (result.source == 'text_ambiguous') {
        setState(() {
          _textMatches = result.matches;
          _error = result.warning ?? 'Có nhiều món phù hợp. Hãy chọn đúng món.';
          _stage = CaptureStage.ready;
        });
        return;
      }
      if (result.source == 'text_not_found') {
        setState(() {
          _textMatches = const [];
          _error = result.error ?? 'Chưa tìm thấy dữ liệu cho món này.';
          _stage = CaptureStage.ready;
        });
        return;
      }
      await Navigator.of(context).pushReplacement(
        BalancePageRoute<void>(
          builder: (_) => AnalysisResultScreen(result: result),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _textMatches = const [];
        _error = error is AnalyzeApiException
            ? error.message
            : 'Chưa kết nối được để phân tích món. Kiểm tra mạng rồi thử lại.';
        _stage = CaptureStage.ready;
      });
    } finally {
      if (mounted && _stage.isAnalyzing) {
        setState(() => _stage = CaptureStage.ready);
      }
    }
  }

  void _selectTextMatch(AnalyzeMatch match) {
    setState(() {
      _foodNameController.value = TextEditingValue(
        text: match.canonicalName,
        selection: TextSelection.collapsed(offset: match.canonicalName.length),
      );
      _textMatches = const [];
      _error = null;
    });
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
          _captureSource = source == ImageSource.camera ? 'camera' : 'upload';
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
            captureSource: _captureSource,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is AnalyzeApiException
            ? error.message
            : 'Chưa kết nối được để phân tích ảnh. Kiểm tra mạng rồi thử lại.';
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
          title: _textMode ? 'Nhập món ăn' : 'Chụp món ăn',
          subtitle: _textMode
              ? 'Nhập tên món khi bạn không có ảnh'
              : 'Chọn ảnh rõ món ăn để Balance phân tích',
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
                    _AnalysisModeSwitcher(
                      textMode: _textMode,
                      onImage: () => _setTextMode(false),
                      onText: () => _setTextMode(true),
                    ),
                    const SizedBox(height: 12),
                    if (_textMode)
                      _TextAnalyzePanel(
                        foodNameController: _foodNameController,
                        gramsController: _gramsController,
                        matches: _textMatches,
                        analyzing: _stage.isAnalyzing,
                        error: _error,
                        onSubmit: _analyzeTypedFood,
                        onSelectMatch: _selectTextMatch,
                      )
                    else
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
                                  onCamera: () =>
                                      _pickImage(ImageSource.camera),
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

class _AnalysisModeSwitcher extends StatelessWidget {
  const _AnalysisModeSwitcher({
    required this.textMode,
    required this.onImage,
    required this.onText,
  });

  final bool textMode;
  final VoidCallback onImage;
  final VoidCallback onText;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: ChoiceChip(
            label: const Text('Chụp ảnh'),
            selected: !textMode,
            onSelected: (_) => onImage(),
            showCheckmark: false,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: ChoiceChip(
            label: const Text('Nhập món'),
            selected: textMode,
            onSelected: (_) => onText(),
            showCheckmark: false,
          ),
        ),
      ],
    );
  }
}

class _TextAnalyzePanel extends StatelessWidget {
  const _TextAnalyzePanel({
    required this.foodNameController,
    required this.gramsController,
    required this.matches,
    required this.analyzing,
    required this.error,
    required this.onSubmit,
    required this.onSelectMatch,
  });

  final TextEditingController foodNameController;
  final TextEditingController gramsController;
  final List<AnalyzeMatch> matches;
  final bool analyzing;
  final String? error;
  final VoidCallback onSubmit;
  final ValueChanged<AnalyzeMatch> onSelectMatch;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      key: const ValueKey('text-analyze-panel'),
      padding: const EdgeInsets.all(18),
      radius: BalanceRadii.card,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Không có ảnh? Nhập món bạn đang nghĩ tới.',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 6),
          Text(
            'Mặc định 100g, bạn có thể chỉnh khối lượng trước khi phân tích.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          TextField(
            key: const ValueKey('text-food-name'),
            controller: foodNameController,
            enabled: !analyzing,
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'Tên món ăn',
              hintText: 'Ví dụ: phở bò, cơm tấm, sữa bò tươi',
              prefixIcon: Icon(Icons.search_rounded),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            key: const ValueKey('text-food-grams'),
            controller: gramsController,
            enabled: !analyzing,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Khối lượng',
              suffixText: 'g',
              prefixIcon: Icon(Icons.scale_outlined),
            ),
          ),
          if (error case final message?) ...[
            const SizedBox(height: 10),
            Text(
              message,
              key: const ValueKey('text-analyze-error'),
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          if (matches.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text(
              'Chọn đúng món để dùng số liệu tương ứng:',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            for (final match in matches)
              _TextMatchTile(match: match, onTap: () => onSelectMatch(match)),
          ],
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const ValueKey('text-analyze-submit'),
            onPressed: analyzing ? null : onSubmit,
            icon: analyzing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.analytics_outlined),
            label: Text(analyzing ? 'Đang phân tích...' : 'Phân tích món'),
          ),
        ],
      ),
    );
  }
}

class _TextMatchTile extends StatelessWidget {
  const _TextMatchTile({required this.match, required this.onTap});

  final AnalyzeMatch match;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: BalanceColors.ink, width: 1.5),
          borderRadius: BorderRadius.circular(BalanceRadii.control),
          color: BalanceColors.paper,
        ),
        child: Material(
          color: Colors.transparent,
          borderRadius: BorderRadius.circular(BalanceRadii.control),
          clipBehavior: Clip.antiAlias,
          child: ListTile(
            key: ValueKey('text-match-${match.recordId}'),
            dense: true,
            title: Text(match.canonicalName),
            subtitle: Text('${_catalogLabel(match)} · ${_basisLabel(match)}'),
            trailing: const Icon(Icons.chevron_right_rounded),
            onTap: onTap,
          ),
        ),
      ),
    );
  }
}

String _catalogLabel(AnalyzeMatch match) {
  return switch (match.catalogType) {
    'vn_dish' => 'Dữ liệu catalog món',
    'vn_ingredient' => 'Dữ liệu nguyên liệu',
    'nrihcm_food' => 'Dữ liệu Viện Dinh dưỡng đã craw',
    _ => match.source,
  };
}

String _basisLabel(AnalyzeMatch match) {
  return switch (match.nutritionBasis) {
    'per_gram' => 'theo gram',
    'per_100g' => 'trên 100g',
    'source_serving' => 'theo khẩu phần nguồn',
    _ => match.nutritionBasis,
  };
}
