import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
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
    return Scaffold(
      appBar: AppBar(title: const Text('Nhu cầu dinh dưỡng')),
      body: GraphPaperBackground(
        child: SafeArea(
          child: _details == null
              ? _LoadingState(error: _error, onRetry: _load)
              : _NutritionDetailsBody(details: _details!),
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
      return const Center(child: CircularProgressIndicator());
    }
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Chưa tải được bảng nhu cầu dinh dưỡng.',
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            FilledButton(onPressed: onRetry, child: const Text('Thử lại')),
          ],
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
        Text(
          'Nhu cầu trong một ngày',
          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
            color: BalanceColors.blueDark,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 12),
        SketchCard(
          color: BalanceColors.paper,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
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
        if (details.warnings.isNotEmpty) ...[
          const SizedBox(height: 12),
          SketchCard(
            color: const Color(0xFFFFF4D6),
            child: Text(
              details.warnings.join('\n'),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
        const SizedBox(height: 16),
        _TargetTable(rows: details.dailyTargets),
      ],
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
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(14),
            color: BalanceColors.blueDark,
            child: const Text(
              'Khuyến nghị trong ngày',
              style: TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w900,
                fontSize: 17,
              ),
            ),
          ),
          for (final row in rows)
            ListTile(
              dense: true,
              title: Text(
                row.nameVi,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(row.unit),
              trailing: Text(
                row.displayValue,
                style: const TextStyle(
                  color: BalanceColors.blueDark,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
        ],
      ),
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
      padding: const EdgeInsets.symmetric(vertical: 5),
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

String _label(String value) => switch (value) {
  'underweight' => 'Thiếu cân',
  'overweight' => 'Thừa cân',
  'obesity' => 'Béo phì',
  _ => 'Bình thường',
};
