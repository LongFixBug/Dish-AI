import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/suggestions/data/suggestions_api.dart';
import 'package:balance/features/suggestions/domain/suggested_dish.dart';
import 'package:flutter/material.dart';

class SuggestionsScreen extends StatelessWidget {
  const SuggestionsScreen({this.gateway, this.animationSeed = 0, super.key});

  /// Bỏ trống thì gọi backend thật; test tiêm bản giả.
  final SuggestionsGateway? gateway;
  final int animationSeed;

  @override
  Widget build(BuildContext context) {
    return BalanceScreenMotion(
      seed: animationSeed,
      child: Scaffold(
        appBar: const BalanceAppBar(title: 'Gợi ý cho bạn'),
        body: GraphPaperBackground(
          child: SafeArea(
            top: false,
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 28),
              child: _SuggestionsContent(gateway: gateway),
            ),
          ),
        ),
      ),
    );
  }
}

class _SuggestionsContent extends StatefulWidget {
  const _SuggestionsContent({this.gateway});

  final SuggestionsGateway? gateway;

  @override
  State<_SuggestionsContent> createState() => _SuggestionsContentState();
}

class _SuggestionsContentState extends State<_SuggestionsContent> {
  SuggestionsApi? _ownApi;
  Future<SuggestionResult>? _request;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _request ??= _load();
  }

  @override
  void dispose() {
    _ownApi?.close();
    super.dispose();
  }

  Future<SuggestionResult> _load() async {
    final state = AppScope.maybeOf(context);
    if (state == null) throw const SuggestionsApiException('Chưa đăng nhập.');
    final gateway = widget.gateway ?? (_ownApi ??= SuggestionsApi());
    final today = state.entriesForDate(DateTime.now());
    final token = await state.validAccessToken();
    return gateway.fetch(
      accessToken: token,
      query: SuggestionQuery(
        consumedCalories: today.fold<double>(0, (a, e) => a + e.calories),
        consumedProtein: today.fold<double>(0, (a, e) => a + e.proteinGrams),
        consumedFat: today.fold<double>(0, (a, e) => a + e.fatGrams),
        consumedCarbs: today.fold<double>(0, (a, e) => a + e.carbsGrams),
        // Đã ăn hôm nay rồi thì đừng gợi ý lại đúng món đó.
        excludeDishNames: today.map((entry) => entry.dishName).toList(),
        allergies: state.profile?.allergies ?? const [],
        preferences: state.preferences.toList(),
      ),
    );
  }

  Future<void> _addToJournal(SuggestedDish dish) async {
    final state = AppScope.maybeOf(context);
    if (state == null) return;
    final now = DateTime.now();
    final entry = JournalEntry(
      id: '${now.microsecondsSinceEpoch}-${dish.dishName}',
      dishName: dish.dishName,
      loggedAt: now,
      mealType: _mealTypeFor(now),
      calories: dish.calories,
      proteinGrams: dish.proteinGrams,
      fatGrams: dish.fatGrams,
      carbsGrams: dish.carbsGrams,
      fiberGrams: 0,
      totalGrams: dish.grams,
    );
    await state.addJournalEntry(entry);
    await state.syncJournalEntry(entry, source: 'suggestion');
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        elevation: 0,
        backgroundColor: BalanceColors.paper,
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 18),
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: BalanceColors.ink, width: 2),
          borderRadius: BorderRadius.circular(12),
        ),
        content: Row(
          children: [
            Container(
              width: 30,
              height: 30,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: BalanceColors.green.withValues(alpha: 0.28),
                border: Border.all(color: BalanceColors.ink, width: 1.4),
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.check_rounded, size: 19),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Đã thêm ${dish.dishName} vào nhật ký',
                style: const TextStyle(
                  color: BalanceColors.ink,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          ],
        ),
      ),
    );
    // Ăn xong thì khoảng trống đổi, gợi ý cũ không còn đúng nữa.
    setState(() {
      _request = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final preferences = state?.preferences ?? AppState.defaultPreferences;
    final hasSafetyFlags = state?.profile?.hasNutritionSafetyFlags ?? false;
    return FutureBuilder<SuggestionResult>(
      future: _request,
      builder: (context, snapshot) {
        final results = _results(snapshot);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            BalanceReveal(
              index: 0,
              child: _RemainingCaloriesCard(
                calories: (snapshot.data?.remaining.calories ?? 0).round(),
                loading: snapshot.connectionState == ConnectionState.waiting,
              ),
            ),
            const SizedBox(height: 12),
            BalanceReveal(
              index: 1,
              child: _SuggestionDisclaimer(hasSafetyFlags: hasSafetyFlags),
            ),
            const SizedBox(height: 18),
            for (var i = 0; i < results.length; i++)
              BalanceReveal(index: 2 + i.clamp(0, 3), child: results[i]),
            const SizedBox(height: 22),
            BalanceReveal(
              index: 5,
              child: _PreferenceSection(
                preferences: preferences,
                onEdit: state == null
                    ? null
                    : () async {
                        await _editPreferences(context);
                        if (mounted) {
                          setState(() {
                            _request = _load();
                          });
                        }
                      },
              ),
            ),
          ],
        );
      },
    );
  }

  List<Widget> _results(AsyncSnapshot<SuggestionResult> snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const [_LoadingSuggestions()];
    }
    if (snapshot.hasError) {
      return [
        _SuggestionNotice(
          icon: Icons.cloud_off_rounded,
          message: 'Không tải được gợi ý lúc này. Kiểm tra mạng rồi thử lại.',
          onRetry: () => setState(() {
            _request = _load();
          }),
        ),
      ];
    }
    final dishes = snapshot.data?.dishes ?? const <SuggestedDish>[];
    if (dishes.isEmpty) {
      return const [
        _SuggestionNotice(
          icon: Icons.check_circle_outline_rounded,
          message: 'Hôm nay bạn đã ăn đủ rồi, Balance không gợi ý thêm nhé!',
        ),
      ];
    }
    return [
      for (final dish in dishes) ...[
        _SuggestionCard(dish: dish, onAdd: () => _addToJournal(dish)),
        const SizedBox(height: 14),
      ],
    ];
  }
}

MealType _mealTypeFor(DateTime moment) {
  final hour = moment.hour;
  if (hour < 10) return MealType.breakfast;
  if (hour < 15) return MealType.lunch;
  if (hour < 21) return MealType.dinner;
  return MealType.snack;
}

/// Thông báo thay cho danh sách khi lỗi hoặc không có gợi ý nào.
class _SuggestionNotice extends StatelessWidget {
  const _SuggestionNotice({
    required this.icon,
    required this.message,
    this.onRetry,
  });

  final IconData icon;
  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      shadow: false,
      child: Column(
        children: [
          Row(
            children: [
              Icon(icon, size: 26),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
              ),
            ],
          ),
          if (onRetry != null) ...[
            const SizedBox(height: 12),
            PressableButton(label: 'Thử lại', onPressed: onRetry),
          ],
        ],
      ),
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
    return Semantics(
      label: 'Lưu ý về gợi ý dinh dưỡng',
      child: SketchCard(
        color: const Color(0xFFFFF3CD),
        shadow: false,
        padding: const EdgeInsets.all(12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.warning_amber_rounded, size: 20),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LoadingSuggestions extends StatelessWidget {
  const _LoadingSuggestions();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 8),
      child: SketchCard(
        shadow: false,
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 24,
              height: 24,
              child: CircularProgressIndicator(
                color: BalanceColors.blueDark,
                strokeWidth: 3,
              ),
            ),
            SizedBox(width: 12),
            Text(
              'Đang tìm món hợp với bạn…',
              style: TextStyle(fontWeight: FontWeight.w800),
            ),
          ],
        ),
      ),
    );
  }
}

class _RemainingCaloriesCard extends StatelessWidget {
  const _RemainingCaloriesCard({required this.calories, this.loading = false});

  final int calories;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: const Color(0xFFFFE69A),
      child: Row(
        children: [
          const Icon(Icons.lightbulb_outline_rounded, size: 42),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Bạn còn', style: TextStyle(fontWeight: FontWeight.w800)),
                if (loading)
                  const Text(
                    'Đang tính…',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900),
                  )
                else
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
            _CompactInkAction(label: 'Chỉnh sửa', onPressed: onEdit),
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
  const _SuggestionCard({required this.dish, required this.onAdd});

  final SuggestedDish dish;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  dish.dishName,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              Text(
                '${dish.calories.round()} kcal',
                style: const TextStyle(
                  fontSize: 19,
                  fontWeight: FontWeight.w900,
                  color: BalanceColors.blueDark,
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            '${dish.grams.round()} g · đạm ${dish.proteinGrams.round()}g · '
            'carb ${dish.carbsGrams.round()}g · béo ${dish.fatGrams.round()}g',
            style: const TextStyle(fontSize: 13, color: BalanceColors.muted),
          ),
          if (dish.reason.isNotEmpty) ...[
            const SizedBox(height: 8),
            // Gợi ý nói được lý do thì người dùng tin và bấm; gợi ý im lặng
            // thì bị lướt qua.
            _SuggestionReasonNote(message: dish.reason),
          ],
          const SizedBox(height: 10),
          PressableButton(
            label: 'Thêm vào nhật ký',
            icon: Icons.add_circle_outline_rounded,
            onPressed: onAdd,
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
    backgroundColor: Colors.transparent,
    elevation: 0,
    barrierColor: BalanceColors.ink.withValues(alpha: 0.36),
    builder: (sheetContext) => StatefulBuilder(
      builder: (context, setModalState) => SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
          child: GraphPaperBackground(
            child: SketchCard(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 42,
                        height: 42,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          color: BalanceColors.yellow,
                          border: Border.all(
                            color: BalanceColors.ink,
                            width: 1.8,
                          ),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: const Icon(Icons.tune_rounded, size: 23),
                      ),
                      const SizedBox(width: 11),
                      Expanded(
                        child: Text(
                          'Sở thích ăn uống',
                          style: Theme.of(context).textTheme.headlineSmall,
                        ),
                      ),
                      _SheetCloseButton(
                        onPressed: () => Navigator.of(sheetContext).pop(),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Chọn những điều bạn muốn ưu tiên',
                    style: TextStyle(
                      color: BalanceColors.muted,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 12),
                  for (final option in options) ...[
                    _PreferenceOption(
                      key: ValueKey('preference-option-$option'),
                      label: option,
                      selected: selected.contains(option),
                      onPressed: () {
                        setModalState(() {
                          selected.contains(option)
                              ? selected.remove(option)
                              : selected.add(option);
                        });
                      },
                    ),
                    if (option != options.last) const SizedBox(height: 8),
                  ],
                  const SizedBox(height: 14),
                  PressableButton(
                    label: 'Lưu sở thích',
                    icon: Icons.check_rounded,
                    onPressed: () => Navigator.of(sheetContext).pop(true),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
  if (saved != true || !context.mounted) return;
  await state.updatePreferences(selected);
}

class _CompactInkAction extends StatelessWidget {
  const _CompactInkAction({required this.label, required this.onPressed});

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Semantics(
      button: true,
      enabled: enabled,
      child: GestureDetector(
        onTap: onPressed,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            color: enabled ? BalanceColors.paper : BalanceColors.paperBlue,
            border: Border.all(color: BalanceColors.ink, width: 1.6),
            borderRadius: BorderRadius.circular(9),
            boxShadow: enabled
                ? const [
                    BoxShadow(color: BalanceColors.ink, offset: Offset(2, 3)),
                  ]
                : null,
          ),
          child: Text(
            label,
            style: TextStyle(
              color: enabled ? BalanceColors.blueDark : BalanceColors.muted,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
      ),
    );
  }
}

class _SuggestionReasonNote extends StatelessWidget {
  const _SuggestionReasonNote({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: BalanceColors.paperBlue,
        border: Border.all(color: BalanceColors.ink, width: 1.4),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.tips_and_updates_outlined, size: 17),
          const SizedBox(width: 7),
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

class _SheetCloseButton extends StatelessWidget {
  const _SheetCloseButton({required this.onPressed});

  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Đóng chỉnh sửa sở thích',
      child: GestureDetector(
        onTap: onPressed,
        child: Container(
          width: 38,
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: BalanceColors.paper,
            border: Border.all(color: BalanceColors.ink, width: 1.7),
            borderRadius: BorderRadius.circular(11),
          ),
          child: const Icon(Icons.close_rounded, size: 21),
        ),
      ),
    );
  }
}

class _PreferenceOption extends StatelessWidget {
  const _PreferenceOption({
    required this.label,
    required this.selected,
    required this.onPressed,
    super.key,
  });

  final String label;
  final bool selected;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      checked: selected,
      label: label,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
          decoration: BoxDecoration(
            color: selected ? _preferenceColor(label) : BalanceColors.paper,
            border: Border.all(color: BalanceColors.ink, width: 1.8),
            borderRadius: BorderRadius.circular(10),
            boxShadow: selected
                ? const [
                    BoxShadow(color: BalanceColors.ink, offset: Offset(2, 3)),
                  ]
                : null,
          ),
          child: Row(
            children: [
              Container(
                width: 22,
                height: 22,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: selected ? BalanceColors.green : BalanceColors.paper,
                  border: Border.all(color: BalanceColors.ink, width: 1.5),
                  borderRadius: BorderRadius.circular(7),
                ),
                child: selected
                    ? const Icon(Icons.check_rounded, size: 16)
                    : null,
              ),
              const SizedBox(width: 10),
              Text(label, style: const TextStyle(fontWeight: FontWeight.w900)),
            ],
          ),
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

Color _preferenceColor(String preference) => switch (preference) {
  'Nhiều đạm' => const Color(0xFFE0F6CE),
  'Ít dầu' => const Color(0xFFE1EDFF),
  'Món Việt' => const Color(0xFFFFE2C8),
  'Ăn chay' => const Color(0xFFE7F7DB),
  _ => const Color(0xFFFFE7CB),
};
