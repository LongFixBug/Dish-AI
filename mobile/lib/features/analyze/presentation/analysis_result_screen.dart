import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_bottom_bar.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/data/feedback_api.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/analyze/presentation/quick_feedback_card.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:flutter/material.dart';

class AnalysisResultScreen extends StatefulWidget {
  const AnalysisResultScreen({
    required this.result,
    this.imageBytes,
    this.stickerBytes,
    this.feedbackGateway,
    super.key,
  });

  /// PNG đã tách nền kèm viền trắng; ``null`` thì rơi về ảnh gốc.
  final Uint8List? stickerBytes;

  /// Tiêm được để test không chạm mạng.
  final FeedbackGateway? feedbackGateway;

  final AnalyzeResult result;
  final Uint8List? imageBytes;

  @override
  State<AnalysisResultScreen> createState() => _AnalysisResultScreenState();
}

class _AnalysisResultScreenState extends State<AnalysisResultScreen> {
  late AnalyzeResult _result = widget.result;
  bool _saving = false;
  bool _saved = false;
  QuickVerdict _verdict = QuickVerdict.none;

  /// Id của entry đã lưu cho chính bữa ăn này, để lần lưu sau ghi đè thay vì
  /// thêm mới — sửa khẩu phần rồi lưu lại không được đếm thành hai bữa.
  String? _savedEntryId;

  Future<void> _saveToJournal() async {
    if (_saving || _saved) return;
    final state = AppScope.maybeOf(context);
    if (state == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã thêm bữa ăn vào nhật ký')),
      );
      return;
    }
    setState(() => _saving = true);
    final now = DateTime.now();
    try {
      final entry = JournalEntry.fromAnalysis(
        result: _result,
        loggedAt: now,
        mealType: _mealTypeFor(now),
        id: _savedEntryId,
      );
      final previousId = _savedEntryId;
      if (previousId != null) {
        await state.removeJournalEntry(previousId);
      }
      await state.addJournalEntry(entry, stickerBytes: widget.stickerBytes);
      final synced = await state.syncJournalEntry(entry, source: 'analyze');
      if (!mounted) return;
      _savedEntryId = entry.id;
      setState(() => _saved = true);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            synced
                ? 'Đã lưu bữa ăn vào nhật ký và đồng bộ tài khoản'
                : 'Đã lưu bữa ăn vào nhật ký trên máy',
          ),
        ),
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Không thể lưu nhật ký. Hãy thử lại.')),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _editPortion() async {
    final initialGrams = _result.nutrition?.totalGrams ?? 0;
    if (initialGrams <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Kết quả này chưa có khối lượng để sửa.')),
      );
      return;
    }
    final grams = await showDialog<double>(
      context: context,
      builder: (_) => _PortionDialog(initialGrams: initialGrams),
    );
    if (grams == null || !mounted) return;
    setState(() {
      _result = _result.scaled(grams / initialGrams);
      _saved = false;
    });
  }

  void _markRecognitionGood() {
    setState(() => _verdict = QuickVerdict.good);
  }

  /// Người dùng bảo nhận diện sai: hỏi tên đúng, sửa ngay trên máy, và chỉ
  /// gửi ảnh đi khi họ tự tích ô đồng ý.
  Future<void> _reportRecognitionWrong() async {
    final input = await showDialog<CorrectionInput>(
      context: context,
      builder: (_) => CorrectionDialog(initialName: _result.dishName ?? ''),
    );
    if (input == null || !mounted) return;

    setState(() {
      _result = _result.renamed(input.dishName);
      _verdict = QuickVerdict.thanks;
      _saved = false;
    });

    if (!input.shareImage) return;
    final bytes = widget.imageBytes;
    final state = AppScope.maybeOf(context);
    if (bytes == null || state == null) return;
    final gateway = widget.feedbackGateway ?? FeedbackApi();
    try {
      final token = await state.validAccessToken();
      await gateway.submitCorrection(
        imageBytes: bytes,
        filename: 'correction.jpg',
        correctDishName: input.dishName,
        consentToTraining: true,
        accessToken: token,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã gửi ảnh góp ý. Cảm ơn bạn!')),
      );
    } on Object {
      if (!mounted) return;
      // Tên món đã sửa xong trên máy rồi, nên lỗi mạng chỉ là mất phần đóng
      // góp cho việc huấn luyện — không được làm hỏng kết quả đang xem.
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Chưa gửi được ảnh góp ý, nhưng tên món đã được sửa.'),
        ),
      );
    }
  }

  void _updateComponentGrams(int index, double grams) {
    setState(() {
      _result = _result.scaledItem(index, grams);
      _saved = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: BalanceBottomBar(
        currentIndex: -1,
        // Màn hình kết quả nằm chồng lên khung chính, nên bấm một tab là
        // đóng cả chồng màn hình rồi mở khung chính đúng tab đó — người dùng
        // không bị kẹt lại nhiều lớp lịch sử phía sau.
        onHomePressed: () => _openShell(context, ShellTab.home),
        onJournalPressed: () => _openShell(context, ShellTab.journal),
        onCameraPressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const AnalyzeScreen()),
        ),
        onSuggestionsPressed: () => _openShell(context, ShellTab.suggestions),
        onProfilePressed: () => _openShell(context, ShellTab.profile),
      ),
      appBar: AppBar(
        title: const Text('Kết quả phân tích'),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
      ),
      body: GraphPaperBackground(
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 24),
            child: _ResultContent(
              result: _result,
              imageBytes: widget.imageBytes,
              stickerBytes: widget.stickerBytes,
              saving: _saving,
              saved: _saved,
              verdict: _verdict,
              onSave: _saveToJournal,
              onEdit: _editPortion,
              onComponentGramsChanged: _updateComponentGrams,
              onRecognitionGood: _markRecognitionGood,
              onRecognitionWrong: _reportRecognitionWrong,
            ),
          ),
        ),
      ),
    );
  }
}

class _PortionDialog extends StatefulWidget {
  const _PortionDialog({required this.initialGrams});

  final double initialGrams;

  @override
  State<_PortionDialog> createState() => _PortionDialogState();
}

class _PortionDialogState extends State<_PortionDialog> {
  double? _grams;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Chỉnh khẩu phần'),
      content: TextFormField(
        key: const ValueKey('portion-grams'),
        initialValue: widget.initialGrams.round().toString(),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        autofocus: true,
        decoration: const InputDecoration(labelText: 'Tổng khối lượng (g)'),
        onChanged: (value) => _grams = double.tryParse(value.trim()),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        FilledButton(
          onPressed: () {
            final value = _grams ?? widget.initialGrams;
            Navigator.of(context).pop(value > 0 ? value : null);
          },
          child: const Text('Áp dụng'),
        ),
      ],
    );
  }
}

class _ResultContent extends StatelessWidget {
  const _ResultContent({
    required this.result,
    required this.imageBytes,
    required this.stickerBytes,
    required this.saving,
    required this.saved,
    required this.verdict,
    required this.onSave,
    required this.onEdit,
    required this.onComponentGramsChanged,
    required this.onRecognitionGood,
    required this.onRecognitionWrong,
  });

  final AnalyzeResult result;
  final Uint8List? imageBytes;
  final Uint8List? stickerBytes;
  final bool saving;
  final bool saved;
  final QuickVerdict verdict;
  final VoidCallback onSave;
  final VoidCallback onEdit;
  final void Function(int index, double grams) onComponentGramsChanged;
  final VoidCallback onRecognitionGood;
  final VoidCallback onRecognitionWrong;

  @override
  Widget build(BuildContext context) {
    final nutrition = result.nutrition;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _ResultSummary(
          result: result,
          imageBytes: imageBytes,
          stickerBytes: stickerBytes,
        ),
        const SizedBox(height: 14),
        if (nutrition != null) _MacroRow(nutrition: nutrition),
        const SizedBox(height: 12),
        QuickFeedbackCard(
          verdict: verdict,
          onGood: onRecognitionGood,
          onWrong: onRecognitionWrong,
        ),
        const SizedBox(height: 12),
        const _NutritionDisclaimer(),
        const SizedBox(height: 20),
        Row(
          children: [
            Text(
              'Thành phần ước tính',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(width: 5),
            const Icon(Icons.info_outline_rounded, size: 18),
          ],
        ),
        const SizedBox(height: 10),
        ..._componentRows(result, onComponentGramsChanged),
        const SizedBox(height: 18),
        _ResultActions(
          saving: saving,
          saved: saved,
          onSave: onSave,
          onEdit: onEdit,
        ),
      ],
    );
  }
}

class _NutritionDisclaimer extends StatelessWidget {
  const _NutritionDisclaimer();

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'Cảnh báo dinh dưỡng',
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFFFF3CD),
          border: Border.all(color: BalanceColors.ink, width: 1.4),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.health_and_safety_outlined, size: 20),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'Dinh dưỡng được AI ước tính và không thay thế tư vấn y tế '
                'hoặc chuyên gia dinh dưỡng.',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultSummary extends StatelessWidget {
  const _ResultSummary({
    required this.result,
    required this.imageBytes,
    this.stickerBytes,
  });

  final AnalyzeResult result;
  final Uint8List? imageBytes;
  final Uint8List? stickerBytes;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      shadow: false,
      padding: const EdgeInsets.all(12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: SizedBox(
              width: 132,
              height: 132,
              child: _ResultImage(
                imageBytes: imageBytes,
                stickerBytes: stickerBytes,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(child: _ResultFacts(result: result)),
        ],
      ),
    );
  }
}

class _ResultImage extends StatelessWidget {
  const _ResultImage({required this.imageBytes, this.stickerBytes});

  final Uint8List? imageBytes;
  final Uint8List? stickerBytes;

  @override
  Widget build(BuildContext context) {
    final sticker = stickerBytes;
    // Sticker đã cắt sát viền nên phải `contain`: `cover` sẽ xén mất chính
    // cái viền trắng vừa tạo ra.
    if (sticker != null && sticker.isNotEmpty) {
      return ColoredBox(
        color: BalanceColors.stickerMat,
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Image.memory(
            sticker,
            key: const ValueKey('result-sticker'),
            fit: BoxFit.contain,
            errorBuilder: (_, _, _) => _RawPhoto(imageBytes: imageBytes),
          ),
        ),
      );
    }
    return _RawPhoto(imageBytes: imageBytes);
  }
}

class _RawPhoto extends StatelessWidget {
  const _RawPhoto({required this.imageBytes});

  final Uint8List? imageBytes;

  @override
  Widget build(BuildContext context) {
    if (imageBytes == null) {
      return const FoodPhoto(meal: FoodPhotoMeal.comTam);
    }
    return Image.memory(
      imageBytes!,
      key: const ValueKey('result-raw-photo'),
      fit: BoxFit.cover,
      errorBuilder: (_, _, _) => const FoodPhoto(meal: FoodPhotoMeal.comTam),
    );
  }
}

class _ResultFacts extends StatelessWidget {
  const _ResultFacts({required this.result});

  final AnalyzeResult result;

  @override
  Widget build(BuildContext context) {
    final recognitionPercent = _recognitionPercent(result);
    final catalogPercent = _catalogCoveragePercent(result);
    final nutrition = result.nutrition;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          result.dishName ?? 'Món ăn đã nhận diện',
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 7),
        const _AiBadge(),
        const SizedBox(height: 14),
        Text(
          // Chưa tra được món nào thì hiện "—", không hiện "0 kcal": con số 0
          // đọc thành "bữa này không có calo" chứ không phải "chưa có dữ liệu".
          nutrition == null
              ? '— kcal'
              : '${_format(nutrition.totalCalories)} kcal',
          style: Theme.of(
            context,
          ).textTheme.displaySmall?.copyWith(color: BalanceColors.blueDark),
        ),
        const SizedBox(height: 4),
        if (recognitionPercent != null)
          Text(
            'Nhận diện: $recognitionPercent%',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        if (catalogPercent != null)
          Text(
            'Dữ liệu catalog: $catalogPercent%',
            style: Theme.of(context).textTheme.bodySmall,
          ),
      ],
    );
  }
}

class _MacroRow extends StatelessWidget {
  const _MacroRow({required this.nutrition});

  final NutritionSummary nutrition;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _MacroCard(
            label: 'Đạm',
            value: nutrition.totalProteinGrams,
            color: const Color(0xFF2E9C45),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MacroCard(
            label: 'Carb',
            value: nutrition.totalCarbsGrams,
            color: BalanceColors.blueDark,
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _MacroCard(
            label: 'Béo',
            value: nutrition.totalFatGrams,
            color: const Color(0xFFE94F14),
          ),
        ),
      ],
    );
  }
}

class _ResultActions extends StatelessWidget {
  const _ResultActions({
    required this.saving,
    required this.saved,
    required this.onSave,
    required this.onEdit,
  });

  final bool saving;
  final bool saved;
  final VoidCallback onSave;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        PressableButton(
          label: saved
              ? 'Đã lưu vào nhật ký'
              : saving
              ? 'Đang lưu...'
              : 'Thêm vào nhật ký',
          icon: saved
              ? Icons.check_circle_outline_rounded
              : Icons.add_circle_outline_rounded,
          backgroundColor: saved ? BalanceColors.green : BalanceColors.blue,
          onPressed: saving || saved ? null : onSave,
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: onEdit,
          icon: const Icon(Icons.edit_outlined),
          label: const Text('Chỉnh sửa'),
          style: OutlinedButton.styleFrom(
            minimumSize: const Size.fromHeight(54),
            foregroundColor: BalanceColors.ink,
            side: const BorderSide(color: BalanceColors.ink, width: 2),
          ),
        ),
      ],
    );
  }
}

class _AiBadge extends StatelessWidget {
  const _AiBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xFFD9F6D9),
        border: Border.all(color: const Color(0xFF198736)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Text(
        '✓ AI nhận diện',
        style: TextStyle(
          color: Color(0xFF146A2B),
          fontWeight: FontWeight.w800,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _MacroCard extends StatelessWidget {
  const _MacroCard({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      shadow: true,
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Column(
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
          Text(
            '${_format(value)} g',
            style: TextStyle(
              color: color,
              fontSize: 24,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

class _ComponentRow extends StatefulWidget {
  const _ComponentRow({
    super.key,
    required this.index,
    required this.name,
    required this.grams,
    required this.calories,
    this.proteinGrams,
    this.fatGrams,
    this.carbsGrams,
    this.onGramsChanged,
  });

  final int index;
  final String name;
  final double grams;
  final double? proteinGrams;
  final double? fatGrams;
  final double? carbsGrams;

  /// ``null`` khi chưa tra được dinh dưỡng — hiện "—" chứ không hiện "0 kcal".
  final double? calories;
  final ValueChanged<double>? onGramsChanged;

  @override
  State<_ComponentRow> createState() => _ComponentRowState();
}

class _ComponentRowState extends State<_ComponentRow> {
  late final TextEditingController _controller;
  bool _editing = false;

  bool get _isEditing => _editing && widget.onGramsChanged != null;

  bool get _hasMacros =>
      (widget.proteinGrams ?? 0) > 0 ||
      (widget.fatGrams ?? 0) > 0 ||
      (widget.carbsGrams ?? 0) > 0;

  String get _caloriesLabel {
    final calories = widget.calories;
    return calories == null ? '— kcal' : '${_format(calories)} kcal';
  }

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: _format(widget.grams));
  }

  @override
  void didUpdateWidget(covariant _ComponentRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.grams != widget.grams &&
        _controller.text != _format(widget.grams)) {
      _controller.value = TextEditingValue(
        text: _format(widget.grams),
        selection: TextSelection.collapsed(
          offset: _format(widget.grams).length,
        ),
      );
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _commit(double grams) {
    final safeGrams = grams.clamp(0.0, 10000.0).toDouble();
    _controller.text = _format(safeGrams);
    widget.onGramsChanged?.call(safeGrams);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: SketchCard(
        shadow: false,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                const CircleAvatar(
                  radius: 17,
                  backgroundColor: BalanceColors.paperBlue,
                  child: Icon(
                    Icons.restaurant_rounded,
                    size: 18,
                    color: BalanceColors.ink,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.name,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      const SizedBox(height: 2),
                      if (_isEditing)
                        Row(
                          children: [
                            _PortionStepper(
                              index: widget.index,
                              controller: _controller,
                              onChanged: (value) {
                                final grams = double.tryParse(value.trim());
                                if (grams != null) {
                                  widget.onGramsChanged?.call(grams);
                                }
                              },
                              onDecrement: () => _commit(widget.grams - 10),
                              onIncrement: () => _commit(widget.grams + 10),
                            ),
                            const SizedBox(width: 8),
                            Flexible(
                              child: Text(
                                _caloriesLabel,
                                key: ValueKey(
                                  'component-calories-${widget.index}',
                                ),
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ],
                        )
                      else
                        Text(
                          '${_format(widget.grams)} g  •  $_caloriesLabel',
                          key: ValueKey('component-calories-${widget.index}'),
                          style: const TextStyle(fontSize: 13),
                        ),
                      if (_hasMacros) ...[
                        const SizedBox(height: 5),
                        _MacroChips(
                          proteinGrams: widget.proteinGrams ?? 0,
                          fatGrams: widget.fatGrams ?? 0,
                          carbsGrams: widget.carbsGrams ?? 0,
                        ),
                      ],
                    ],
                  ),
                ),
                if (widget.onGramsChanged != null) ...[
                  const SizedBox(width: 8),
                  _EditToggle(
                    index: widget.index,
                    editing: _editing,
                    onPressed: () => setState(() => _editing = !_editing),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Ba chỉ số macro kèm icon, đọc lướt được mà không cần mở bảng chi tiết.
class _MacroChips extends StatelessWidget {
  const _MacroChips({
    required this.proteinGrams,
    required this.fatGrams,
    required this.carbsGrams,
  });

  final double proteinGrams;
  final double fatGrams;
  final double carbsGrams;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 4,
      children: [
        _MacroChip(
          icon: Icons.grass_rounded,
          color: BalanceColors.blue,
          label: 'Carb',
          grams: carbsGrams,
        ),
        _MacroChip(
          icon: Icons.egg_alt_rounded,
          color: BalanceColors.green,
          label: 'Đạm',
          grams: proteinGrams,
        ),
        _MacroChip(
          icon: Icons.water_drop_rounded,
          color: BalanceColors.orange,
          label: 'Béo',
          grams: fatGrams,
        ),
      ],
    );
  }
}

class _MacroChip extends StatelessWidget {
  const _MacroChip({
    required this.icon,
    required this.color,
    required this.label,
    required this.grams,
  });

  final IconData icon;
  final Color color;
  final String label;
  final double grams;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '$label ${_format(grams)} gam',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 15, color: color),
          const SizedBox(width: 3),
          Text(
            _format(grams),
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

/// Nút mở/đóng chế độ sửa khối lượng.
///
/// Ô nhập luôn mở khiến người dùng chạm nhầm vào bàn phím khi chỉ định cuộn
/// xem kết quả, nên khối lượng chỉ sửa được sau khi bấm nút này.
class _EditToggle extends StatelessWidget {
  const _EditToggle({
    required this.index,
    required this.editing,
    required this.onPressed,
  });

  final int index;
  final bool editing;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: editing ? 'Đóng sửa khối lượng' : 'Sửa khối lượng',
      child: InkWell(
        key: ValueKey('component-edit-toggle-$index'),
        onTap: onPressed,
        borderRadius: BorderRadius.circular(999),
        child: Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: editing ? BalanceColors.blue : BalanceColors.paperBlue,
            shape: BoxShape.circle,
            border: Border.all(color: BalanceColors.ink, width: 1.6),
          ),
          child: Icon(
            editing ? Icons.close_rounded : Icons.remove_rounded,
            size: 20,
            color: editing ? Colors.white : BalanceColors.ink,
          ),
        ),
      ),
    );
  }
}

class _PortionStepper extends StatelessWidget {
  const _PortionStepper({
    required this.index,
    required this.controller,
    required this.onChanged,
    required this.onDecrement,
    required this.onIncrement,
  });

  final int index;
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  final VoidCallback onDecrement;
  final VoidCallback onIncrement;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          key: ValueKey('component-minus-$index'),
          onPressed: onDecrement,
          icon: const Icon(Icons.remove_circle_outline_rounded),
          tooltip: 'Giảm 10 gram',
          visualDensity: VisualDensity.compact,
        ),
        SizedBox(
          width: 58,
          child: TextField(
            key: ValueKey('component-grams-$index'),
            controller: controller,
            onChanged: onChanged,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            textAlign: TextAlign.center,
            decoration: const InputDecoration(
              suffixText: 'g',
              isDense: true,
              contentPadding: EdgeInsets.symmetric(horizontal: 4, vertical: 8),
            ),
          ),
        ),
        IconButton(
          key: ValueKey('component-plus-$index'),
          onPressed: onIncrement,
          icon: const Icon(Icons.add_circle_outline_rounded),
          tooltip: 'Tăng 10 gram',
          visualDensity: VisualDensity.compact,
        ),
      ],
    );
  }
}

List<Widget> _componentRows(
  AnalyzeResult result,
  void Function(int index, double grams) onComponentGramsChanged,
) {
  final items = result.nutrition?.items ?? const <NutritionItem>[];
  if (items.isNotEmpty) {
    return items
        .asMap()
        .entries
        .map(
          (entry) => _ComponentRow(
            key: ValueKey('component-row-${entry.key}'),
            index: entry.key,
            name: entry.value.name,
            grams: entry.value.grams,
            calories: entry.value.calories,
            proteinGrams: entry.value.proteinGrams,
            fatGrams: entry.value.fatGrams,
            carbsGrams: entry.value.carbsGrams,
            onGramsChanged: (grams) =>
                onComponentGramsChanged(entry.key, grams),
          ),
        )
        .toList(growable: false);
  }
  // Không món nào tra được trong catalog: chỉ liệt kê tên, KHÔNG hiện "0 kcal"
  // vì người dùng sẽ đọc thành "món này không có calo" thay vì "chưa có dữ liệu".
  return result.dishes
      .asMap()
      .entries
      .map(
        (entry) => _ComponentRow(
          key: ValueKey('component-row-${entry.key}'),
          index: entry.key,
          name: entry.value.name,
          grams: entry.value.grams,
          calories: null,
        ),
      )
      .toList(growable: false);
}

int? _recognitionPercent(AnalyzeResult result) {
  final score = result.recognitionConfidence ?? result.cvConfidence;
  return score == null ? null : (score * 100).round();
}

int? _catalogCoveragePercent(AnalyzeResult result) {
  final nutrition = result.nutrition;
  return nutrition == null
      ? null
      : (nutrition.catalogCoverageScore * 100).round();
}

String _format(double value) {
  return value == value.roundToDouble()
      ? value.toStringAsFixed(0)
      : value.toStringAsFixed(1);
}

MealType _mealTypeFor(DateTime time) => switch (time.hour) {
  < 10 => MealType.breakfast,
  < 15 => MealType.lunch,
  < 21 => MealType.dinner,
  _ => MealType.snack,
};

void _openShell(BuildContext context, ShellTab tab) {
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute<void>(builder: (_) => MainShell(initialTab: tab)),
    (route) => false,
  );
}
