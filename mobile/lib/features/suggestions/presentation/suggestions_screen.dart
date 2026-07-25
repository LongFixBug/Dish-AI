import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_bottom_bar.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:balance/features/profile/presentation/profile_screen.dart';
import 'package:flutter/material.dart';

class SuggestionsScreen extends StatelessWidget {
  const SuggestionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gợi ý bữa tối'),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
      ),
      bottomNavigationBar: BalanceBottomBar(
        currentIndex: 3,
        onHomePressed: () =>
            Navigator.of(context).popUntil((route) => route.isFirst),
        onJournalPressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const JournalScreen()),
        ),
        onCameraPressed: () => Navigator.of(
          context,
        ).push(MaterialPageRoute<void>(builder: (_) => const AnalyzeScreen())),
        onProfilePressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const ProfileScreen()),
        ),
      ),
      body: GraphPaperBackground(
        child: SafeArea(
          top: false,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 28),
            child: const _SuggestionsContent(),
          ),
        ),
      ),
    );
  }
}

class _SuggestionsContent extends StatelessWidget {
  const _SuggestionsContent();

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final target = state?.profile?.dailyCalorieTarget ?? 1800;
    final consumed = state?.todayCalories(DateTime.now()) ?? 1240;
    final remaining = (target - consumed).round().clamp(0, 4000);
    final preferences = state?.preferences ?? AppState.defaultPreferences;
    final hasSafetyFlags = state?.profile?.hasNutritionSafetyFlags ?? false;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _RemainingCaloriesCard(calories: remaining),
        const SizedBox(height: 12),
        _SuggestionDisclaimer(hasSafetyFlags: hasSafetyFlags),
        const SizedBox(height: 18),
        const _SuggestionCard(
          meal: FoodPhotoMeal.caKho,
          background: Color(0xFFE3F6D7),
          name: 'Cá kho tộ + cơm',
          calories: 520,
          protein: 28,
          carbs: 64,
          fat: 16,
        ),
        const SizedBox(height: 16),
        const _SuggestionCard(
          meal: FoodPhotoMeal.bunGa,
          background: Color(0xFFFFE1BE),
          name: 'Bún gà rau củ',
          calories: 480,
          protein: 28,
          carbs: 54,
          fat: 14,
        ),
        const SizedBox(height: 22),
        _PreferenceSection(
          preferences: preferences,
          onEdit: state == null ? null : () => _editPreferences(context),
        ),
        const SizedBox(height: 18),
        PressableButton(
          label: 'Xem thực đơn',
          icon: Icons.restaurant_menu_rounded,
          backgroundColor: BalanceColors.yellow,
          foregroundColor: BalanceColors.ink,
          onPressed: () => _showWeeklyMenu(context),
        ),
      ],
    );
  }
}

class _SuggestionDisclaimer extends StatelessWidget {
  const _SuggestionDisclaimer({required this.hasSafetyFlags});

  final bool hasSafetyFlags;

  @override
  Widget build(BuildContext context) {
    final message = hasSafetyFlags
        ? 'Các món chỉ để tham khảo, chưa kiểm tra dị ứng hoặc bệnh nền của '
              'bạn. Hãy xác nhận thành phần trước khi dùng.'
        : 'Các món chỉ để tham khảo và chưa kiểm tra dị ứng. Hãy xác nhận '
              'thành phần trước khi dùng.';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3CD),
        border: Border.all(color: BalanceColors.ink, width: 1.4),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.warning_amber_rounded, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _RemainingCaloriesCard extends StatelessWidget {
  const _RemainingCaloriesCard({required this.calories});

  final int calories;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: Color(0xFFFFE69A),
      child: Row(
        children: [
          Icon(Icons.lightbulb_outline_rounded, size: 42),
          SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Bạn còn', style: TextStyle(fontWeight: FontWeight.w800)),
                Text.rich(
                  TextSpan(
                    children: [
                      TextSpan(
                        text: '$calories ',
                        style: const TextStyle(
                          fontSize: 34,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const TextSpan(
                        text: 'kcal hôm nay',
                        style: TextStyle(fontWeight: FontWeight.w800),
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

class _PreferenceSection extends StatelessWidget {
  const _PreferenceSection({required this.preferences, required this.onEdit});

  final Set<String> preferences;
  final VoidCallback? onEdit;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              'Sở thích của bạn',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            TextButton(onPressed: onEdit, child: const Text('Chỉnh sửa')),
          ],
        ),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final preference in preferences)
              _PreferenceChip(
                label: preference,
                color: _preferenceColor(preference),
              ),
          ],
        ),
      ],
    );
  }
}

class _SuggestionCard extends StatelessWidget {
  const _SuggestionCard({
    required this.meal,
    required this.background,
    required this.name,
    required this.calories,
    required this.protein,
    required this.carbs,
    required this.fat,
  });

  final FoodPhotoMeal meal;
  final Color background;
  final String name;
  final int calories;
  final int protein;
  final int carbs;
  final int fat;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: background,
      padding: const EdgeInsets.all(10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(9),
            child: SizedBox(
              width: 142,
              height: 154,
              child: FoodPhoto(meal: meal),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(
                        name,
                        style: Theme.of(
                          context,
                        ).textTheme.headlineSmall?.copyWith(fontSize: 22),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Lưu món gợi ý',
                      visualDensity: VisualDensity.compact,
                      onPressed: () =>
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Đã lưu gợi ý $name')),
                          ),
                      icon: const Icon(Icons.bookmark_border_rounded),
                    ),
                  ],
                ),
                const SizedBox(height: 5),
                Text(
                  '$calories kcal',
                  style: const TextStyle(
                    color: Color(0xFF228238),
                    fontSize: 25,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    _TinyMacro('Đạm', protein, const Color(0xFF208B36)),
                    const SizedBox(width: 5),
                    _TinyMacro('Carb', carbs, BalanceColors.blueDark),
                    const SizedBox(width: 5),
                    _TinyMacro('Béo', fat, const Color(0xFFE94F14)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

Future<void> _editPreferences(BuildContext context) async {
  final state = AppScope.of(context);
  final selected = {...state.preferences};
  const options = ['Nhiều đạm', 'Ít dầu', 'Món Việt', 'Ăn chay', 'Ít carb'];
  final saved = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (sheetContext) => StatefulBuilder(
      builder: (context, setModalState) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Sở thích ăn uống',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 12),
              for (final option in options)
                CheckboxListTile(
                  value: selected.contains(option),
                  title: Text(option),
                  onChanged: (checked) {
                    setModalState(() {
                      checked == true
                          ? selected.add(option)
                          : selected.remove(option);
                    });
                  },
                ),
              const SizedBox(height: 10),
              PressableButton(
                label: 'Lưu sở thích',
                onPressed: () => Navigator.of(sheetContext).pop(true),
              ),
            ],
          ),
        ),
      ),
    ),
  );
  if (saved != true || !context.mounted) return;
  await state.updatePreferences(selected);
}

Future<void> _showWeeklyMenu(BuildContext context) {
  return showModalBottomSheet<void>(
    context: context,
    builder: (context) => const SafeArea(
      child: Padding(
        padding: EdgeInsets.fromLTRB(20, 18, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Thực đơn cân bằng',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
            ),
            SizedBox(height: 14),
            Text('Thứ Hai • Cá kho tộ + cơm'),
            Text('Thứ Ba • Bún gà rau củ'),
            Text('Thứ Tư • Cơm tấm sườn'),
            Text('Thứ Năm • Phở bò'),
            Text('Thứ Sáu • Cá hấp + rau luộc'),
          ],
        ),
      ),
    ),
  );
}

Color _preferenceColor(String preference) => switch (preference) {
  'Nhiều đạm' => const Color(0xFFE0F6CE),
  'Ít dầu' => const Color(0xFFE1EDFF),
  'Món Việt' => const Color(0xFFFFE2C8),
  'Ăn chay' => const Color(0xFFE7F7DB),
  _ => const Color(0xFFFFE7CB),
};

class _TinyMacro extends StatelessWidget {
  const _TinyMacro(this.label, this.value, this.color);

  final String label;
  final int value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 5),
        decoration: BoxDecoration(
          color: BalanceColors.paper,
          border: Border.all(color: BalanceColors.ink, width: 1.5),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Column(
          children: [
            Text(label, style: const TextStyle(fontSize: 10)),
            Text(
              '${value}g',
              style: TextStyle(color: color, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class _PreferenceChip extends StatelessWidget {
  const _PreferenceChip({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 9),
      decoration: BoxDecoration(
        color: color,
        border: Border.all(color: BalanceColors.ink, width: 1.6),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(width: 7),
          const Icon(Icons.check_rounded, size: 17),
        ],
      ),
    );
  }
}
