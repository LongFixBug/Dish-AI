import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/nutrition/data/nutrition_goal_api.dart';
import 'package:flutter/material.dart';

class NutritionGoalScreen extends StatefulWidget {
  const NutritionGoalScreen({super.key});

  @override
  State<NutritionGoalScreen> createState() => _NutritionGoalScreenState();
}

class _NutritionGoalScreenState extends State<NutritionGoalScreen> {
  NutritionGoalDetails? _details;
  Object? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    try {
      final details = await AppScope.maybeOf(context)?.previewNutritionGoal();
      if (!mounted) return;
      setState(() {
        _details = details;
        _error = details == null
            ? StateError('Nutrition detail gateway unavailable')
            : null;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _error = error);
    }
  }

  @override
  Widget build(BuildContext context) {
    return BalanceScreenMotion(
      child: Scaffold(
        appBar: const BalanceAppBar(title: 'Nhu cầu dinh dưỡng'),
        body: GraphPaperBackground(
          child: SafeArea(
            child: _details == null
                ? BalanceReveal(
                    index: 0,
                    child: _LoadingState(error: _error, onRetry: _load),
                  )
                : _NutritionDetailsBody(details: _details!),
          ),
        ),
      ),
    );
  }
}

class _LoadingState extends StatelessWidget {
  const _LoadingState({required this.error, required this.onRetry});

  final Object? error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    if (error == null) {
      return const Center(
        child: SketchCard(
          shadow: false,
          padding: EdgeInsets.symmetric(horizontal: 22, vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                width: 34,
                height: 34,
                child: CircularProgressIndicator(
                  color: BalanceColors.blueDark,
                  strokeWidth: 4,
                ),
              ),
              SizedBox(height: 12),
              Text(
                'Đang dựng bảng dinh dưỡng…',
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
            ],
          ),
        ),
      );
    }
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: SketchCard(
          color: BalanceColors.paper,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 48,
                height: 48,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0xFFFFE4DE),
                  border: Border.all(color: BalanceColors.ink, width: 1.8),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(Icons.cloud_off_rounded, size: 26),
              ),
              const SizedBox(height: 12),
              const Text(
                'Chưa tải được bảng nhu cầu dinh dưỡng.',
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 14),
              PressableButton(
                label: 'Thử lại',
                icon: Icons.refresh_rounded,
                onPressed: onRetry,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NutritionDetailsBody extends StatelessWidget {
  const _NutritionDetailsBody({required this.details});

  final NutritionGoalDetails details;

  @override
  Widget build(BuildContext context) {
    final profile = details.profile;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
      children: [
        BalanceReveal(index: 0, child: _DailyTargetHero(details: details)),
        const SizedBox(height: 14),
        BalanceReveal(
          index: 1,
          child: SketchCard(
            color: BalanceColors.paper,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const _SectionHeading(
                  icon: Icons.person_outline_rounded,
                  label: 'Dữ liệu cơ thể',
                ),
                const SizedBox(height: 8),
                _ProfileLine(label: 'Tuổi', value: '${profile.age} tuổi'),
                _ProfileLine(
                  label: 'Cơ thể',
                  value:
                      '${profile.weightKg.toStringAsFixed(0)} kg · '
                      '${profile.heightCm.toStringAsFixed(0)} cm',
                ),
                _ProfileLine(
                  label: 'BMI',
                  value:
                      '${profile.bmi.toStringAsFixed(1)} · '
                      '${_label(profile.bmiCategory)}',
                ),
                _ProfileLine(
                  label: 'Năng lượng duy trì',
                  value: '${details.maintenanceCalories} kcal',
                ),
              ],
            ),
          ),
        ),
        if (details.warnings.isNotEmpty) ...[
          const SizedBox(height: 12),
          BalanceReveal(
            index: 2,
            child: SketchCard(
              color: const Color(0xFFFFF4D6),
              shadow: false,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.health_and_safety_outlined, size: 23),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      details.warnings.join('\n'),
                      style: const TextStyle(fontWeight: FontWeight.w800),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
        const SizedBox(height: 16),
        BalanceReveal(
          index: details.warnings.isEmpty ? 2 : 3,
          child: _TargetTable(rows: details.dailyTargets),
        ),
      ],
    );
  }
}

class _DailyTargetHero extends StatelessWidget {
  const _DailyTargetHero({required this.details});

  final NutritionGoalDetails details;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: BalanceColors.blue,
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
      child: Row(
        children: [
          Container(
            width: 58,
            height: 58,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: BalanceColors.yellow,
              border: Border.all(color: BalanceColors.ink, width: 2),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(Icons.bolt_rounded, size: 34),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Nhu cầu trong một ngày',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 2),
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: '${details.targetCalories}',
                        style: const TextStyle(
                          color: BalanceColors.yellow,
                          fontSize: 31,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const TextSpan(
                        text: ' kcal / ngày',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
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

class _TargetTable extends StatelessWidget {
  const _TargetTable({required this.rows});

  final List<NutritionTargetRow> rows;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: BalanceColors.paper,
      padding: const EdgeInsets.fromLTRB(14, 13, 14, 8),
      child: Column(
        children: [
          const _SectionHeading(
            icon: Icons.menu_book_outlined,
            label: 'Khuyến nghị trong ngày',
          ),
          const SizedBox(height: 7),
          for (final row in rows)
            _TargetLine(row: row, isLast: identical(row, rows.last)),
        ],
      ),
    );
  }
}

class _SectionHeading extends StatelessWidget {
  const _SectionHeading({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 32,
          height: 32,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: BalanceColors.paperBlue,
            border: Border.all(color: BalanceColors.ink, width: 1.6),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 19),
        ),
        const SizedBox(width: 9),
        Expanded(
          child: Text(label, style: Theme.of(context).textTheme.titleMedium),
        ),
      ],
    );
  }
}

class _TargetLine extends StatelessWidget {
  const _TargetLine({required this.row, required this.isLast});

  final NutritionTargetRow row;
  final bool isLast;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Row(
            children: [
              Container(
                width: 8,
                height: 32,
                decoration: BoxDecoration(
                  color: _targetColor(row.category),
                  border: Border.all(color: BalanceColors.ink, width: 1.1),
                  borderRadius: BorderRadius.circular(5),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      row.nameVi,
                      style: const TextStyle(fontWeight: FontWeight.w900),
                    ),
                    Text(
                      row.unit,
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Text(
                row.displayValue,
                style: const TextStyle(
                  color: BalanceColors.blueDark,
                  fontSize: 17,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
        ),
        if (!isLast)
          Container(
            height: 1,
            color: BalanceColors.ink.withValues(alpha: 0.14),
          ),
      ],
    );
  }
}

class _ProfileLine extends StatelessWidget {
  const _ProfileLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          SizedBox(
            width: 150,
            child: Text(
              label,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
          ),
        ],
      ),
    );
  }
}

Color _targetColor(String category) => switch (category) {
  'energy' => BalanceColors.yellow,
  'macronutrient' => BalanceColors.green,
  _ => BalanceColors.orange,
};

String _label(String value) => switch (value) {
  'underweight' => 'Thiếu cân',
  'overweight' => 'Thừa cân',
  'obesity' => 'Béo phì',
  _ => 'Bình thường',
};
