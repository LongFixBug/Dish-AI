import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_bottom_bar.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:balance/features/profile/presentation/profile_screen.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';

class AnalysisResultScreen extends StatefulWidget {
  const AnalysisResultScreen({
    required this.result,
    this.imageBytes,
    super.key,
  });

  final AnalyzeResult result;
  final Uint8List? imageBytes;

  @override
  State<AnalysisResultScreen> createState() => _AnalysisResultScreenState();
}

class _AnalysisResultScreenState extends State<AnalysisResultScreen> {
  late AnalyzeResult _result = widget.result;
  bool _saving = false;
  bool _saved = false;

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
      await state.addJournalEntry(
        JournalEntry.fromAnalysis(
          result: _result,
          loggedAt: now,
          mealType: _mealTypeFor(now),
        ),
      );
      if (!mounted) return;
      setState(() => _saved = true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Đã lưu bữa ăn vào nhật ký')),
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: BalanceBottomBar(
        currentIndex: -1,
        onHomePressed: () =>
            Navigator.of(context).popUntil((route) => route.isFirst),
        onJournalPressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const JournalScreen()),
        ),
        onCameraPressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const AnalyzeScreen()),
        ),
        onSuggestionsPressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const SuggestionsScreen()),
        ),
        onProfilePressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const ProfileScreen()),
        ),
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
              saving: _saving,
              saved: _saved,
              onSave: _saveToJournal,
              onEdit: _editPortion,
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
    required this.saving,
    required this.saved,
    required this.onSave,
    required this.onEdit,
  });

  final AnalyzeResult result;
  final Uint8List? imageBytes;
  final bool saving;
  final bool saved;
  final VoidCallback onSave;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context) {
    final nutrition = result.nutrition;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _ResultSummary(result: result, imageBytes: imageBytes),
        const SizedBox(height: 14),
        if (nutrition != null) _MacroRow(nutrition: nutrition),
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
        ..._componentRows(result),
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

class _ResultSummary extends StatelessWidget {
  const _ResultSummary({required this.result, required this.imageBytes});

  final AnalyzeResult result;
  final Uint8List? imageBytes;

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
              child: _ResultImage(imageBytes: imageBytes),
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
  const _ResultImage({required this.imageBytes});

  final Uint8List? imageBytes;

  @override
  Widget build(BuildContext context) {
    if (imageBytes == null) {
      return const FoodPhoto(meal: FoodPhotoMeal.comTam);
    }
    return Image.memory(
      imageBytes!,
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
          '${_format(result.nutrition?.totalCalories ?? 0)} kcal',
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

class _ComponentRow extends StatelessWidget {
  const _ComponentRow({
    required this.name,
    required this.grams,
    required this.calories,
  });

  final String name;
  final double grams;
  final double calories;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: SketchCard(
        shadow: false,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
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
                    name,
                    style: const TextStyle(fontWeight: FontWeight.w900),
                  ),
                  Text('${_format(grams)} g'),
                ],
              ),
            ),
            Text('${_format(calories)} kcal'),
            const SizedBox(width: 8),
            const Icon(Icons.edit_outlined, size: 20),
          ],
        ),
      ),
    );
  }
}

List<Widget> _componentRows(AnalyzeResult result) {
  final items = result.nutrition?.items ?? const <NutritionItem>[];
  if (items.isNotEmpty) {
    return items
        .map(
          (item) => _ComponentRow(
            name: item.name,
            grams: item.grams,
            calories: item.calories,
          ),
        )
        .toList(growable: false);
  }
  return result.dishes
      .map(
        (dish) =>
            _ComponentRow(name: dish.name, grams: dish.grams, calories: 0),
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
