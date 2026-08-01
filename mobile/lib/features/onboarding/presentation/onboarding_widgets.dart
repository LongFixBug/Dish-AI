import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/onboarding/presentation/ruler_picker.dart';
import 'package:flutter/material.dart';

class OnboardingProgressHeader extends StatelessWidget {
  const OnboardingProgressHeader({
    required this.step,
    required this.totalSteps,
    required this.onBack,
    super.key,
  });

  final int step;
  final int totalSteps;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 2),
      child: SketchCard(
        padding: const EdgeInsets.fromLTRB(8, 8, 10, 8),
        radius: 16,
        shadow: false,
        child: Row(
          children: [
            BalanceIconButton(
              tooltip: 'Quay lại',
              icon: Icons.arrow_back_rounded,
              onPressed: onBack,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Hồ sơ dinh dưỡng',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 5),
                  Row(
                    children: [
                      Text(
                        'Bước ${step + 1} trong $totalSteps',
                        style: const TextStyle(
                          color: BalanceColors.muted,
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(99),
                          child: LinearProgressIndicator(
                            value: (step + 1) / totalSteps,
                            minHeight: 7,
                            backgroundColor: const Color(0xFFD9D9D9),
                            color: BalanceColors.blue,
                          ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '${step + 1} / $totalSteps',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class OnboardingTitle extends StatelessWidget {
  const OnboardingTitle({
    required this.title,
    required this.subtitle,
    super.key,
  });

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          title,
          textAlign: TextAlign.center,
          style: Theme.of(
            context,
          ).textTheme.displaySmall?.copyWith(fontSize: 34, height: 1.15),
        ),
        const SizedBox(height: 12),
        Text(
          subtitle,
          textAlign: TextAlign.center,
          style: Theme.of(
            context,
          ).textTheme.bodyLarge?.copyWith(color: BalanceColors.muted),
        ),
      ],
    );
  }
}

class NumberStepperCard extends StatelessWidget {
  const NumberStepperCard({
    required this.label,
    required this.value,
    required this.unit,
    required this.onDecrement,
    required this.onIncrement,
    this.decrementKey,
    this.incrementKey,
    this.min,
    this.max,
    this.onSliderChanged,
    super.key,
  });

  final String label;
  final int value;
  final String unit;
  final VoidCallback onDecrement;
  final VoidCallback onIncrement;
  final Key? decrementKey;
  final Key? incrementKey;
  final int? min;
  final int? max;
  final ValueChanged<int>? onSliderChanged;

  bool get _showRuler => min != null && max != null;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        SketchCard(
          padding: EdgeInsets.fromLTRB(14, 14, 14, _showRuler ? 8 : 14),
          radius: 16,
          child: Column(
            children: [
              Row(
                children: [
                  _SquareControl(
                    key: decrementKey,
                    icon: Icons.remove_rounded,
                    tooltip: 'Giảm $label',
                    onTap: onDecrement,
                  ),
                  Expanded(
                    child: Text.rich(
                      TextSpan(
                        children: [
                          TextSpan(
                            text: '$value ',
                            style: const TextStyle(
                              fontSize: 34,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          TextSpan(
                            text: unit,
                            style: const TextStyle(
                              fontSize: 20,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  _SquareControl(
                    key: incrementKey,
                    icon: Icons.add_rounded,
                    tooltip: 'Tăng $label',
                    onTap: onIncrement,
                  ),
                ],
              ),
              if (_showRuler) ...[
                const SizedBox(height: 4),
                RulerPicker(
                  value: value,
                  min: min!,
                  max: max!,
                  onChanged: onSliderChanged!,
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }
}

class _SquareControl extends StatelessWidget {
  const _SquareControl({
    required this.icon,
    required this.tooltip,
    required this.onTap,
    super.key,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return BalanceIconButton(tooltip: tooltip, icon: icon, onPressed: onTap);
  }
}

class GenderOption {
  const GenderOption(this.label, this.icon);

  final String label;
  final IconData icon;
}

class GenderCard extends StatelessWidget {
  const GenderCard({
    required this.option,
    required this.selected,
    required this.onTap,
    super.key,
  });

  final GenderOption option;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final foreground = selected ? Colors.white : BalanceColors.ink;
    return Semantics(
      button: true,
      selected: selected,
      label: option.label,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: AnimatedScale(
          duration: const Duration(milliseconds: 160),
          curve: Curves.easeOutBack,
          scale: selected ? 1 : 0.985,
          child: SketchCard(
            color: selected ? BalanceColors.blue : BalanceColors.paper,
            padding: EdgeInsets.zero,
            radius: 14,
            child: SizedBox(
              height: 148,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(option.icon, size: 48, color: foreground),
                  const SizedBox(height: 8),
                  Text(
                    option.label,
                    style: Theme.of(
                      context,
                    ).textTheme.titleMedium?.copyWith(color: foreground),
                  ),
                  const SizedBox(height: 8),
                  Icon(
                    selected ? Icons.check_circle : Icons.circle_outlined,
                    color: foreground,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ChoiceOption {
  const ChoiceOption(this.title, this.subtitle, this.icon);

  final String title;
  final String subtitle;
  final IconData icon;
}

class ChoiceList extends StatelessWidget {
  const ChoiceList({
    required this.title,
    required this.subtitle,
    required this.options,
    required this.selected,
    required this.selectedColor,
    required this.onSelected,
    super.key,
  });

  final String title;
  final String subtitle;
  final List<ChoiceOption> options;
  final String selected;
  final Color selectedColor;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        OnboardingTitle(title: title, subtitle: subtitle),
        const SizedBox(height: 24),
        for (final option in options) ...[
          _ChoiceTile(
            option: option,
            selected: selected == option.title,
            selectedColor: selectedColor,
            onTap: () => onSelected(option.title),
          ),
          const SizedBox(height: 14),
        ],
      ],
    );
  }
}

class _ChoiceTile extends StatelessWidget {
  const _ChoiceTile({
    required this.option,
    required this.selected,
    required this.selectedColor,
    required this.onTap,
  });

  final ChoiceOption option;
  final bool selected;
  final Color selectedColor;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      label: option.title,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: AnimatedScale(
          duration: const Duration(milliseconds: 160),
          curve: Curves.easeOutBack,
          scale: selected ? 1 : 0.992,
          child: SketchCard(
            color: selected ? selectedColor : BalanceColors.paper,
            radius: 16,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: ConstrainedBox(
              constraints: const BoxConstraints(minHeight: 82),
              child: Row(
                children: [
                  Icon(option.icon, size: 40),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          option.title,
                          style: Theme.of(
                            context,
                          ).textTheme.titleMedium?.copyWith(fontSize: 19),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          option.subtitle,
                          style: Theme.of(context).textTheme.bodyMedium
                              ?.copyWith(
                                color: BalanceColors.ink,
                                height: 1.15,
                              ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Icon(
                    selected ? Icons.check_circle : Icons.circle_outlined,
                    size: 28,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
