import 'package:balance/core/theme/balance_theme.dart';
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
      padding: const EdgeInsets.fromLTRB(14, 10, 20, 0),
      child: Row(
        children: [
          IconButton(
            onPressed: onBack,
            icon: const Icon(Icons.arrow_back_rounded, size: 30),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: LinearProgressIndicator(
                value: (step + 1) / totalSteps,
                minHeight: 9,
                backgroundColor: const Color(0xFFD9D9D9),
                color: BalanceColors.blue,
              ),
            ),
          ),
          const SizedBox(width: 18),
          Text(
            '${step + 1} / $totalSteps',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ],
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
        Container(
          padding: EdgeInsets.fromLTRB(14, 14, 14, _showRuler ? 8 : 14),
          decoration: _raisedDecoration(),
          child: Column(
            children: [
              Row(
                children: [
                  _SquareControl(
                    key: decrementKey,
                    icon: Icons.remove_rounded,
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
                    onTap: onIncrement,
                  ),
                ],
              ),
              if (_showRuler) ...[
                const SizedBox(height: 8),
                _Ruler(
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

BoxDecoration _raisedDecoration({Color color = BalanceColors.paper}) {
  return BoxDecoration(
    color: color,
    border: Border.all(color: BalanceColors.ink, width: 2.5),
    borderRadius: BorderRadius.circular(13),
    boxShadow: const [
      BoxShadow(color: BalanceColors.ink, offset: Offset(4, 6)),
    ],
  );
}

class _SquareControl extends StatelessWidget {
  const _SquareControl({required this.icon, required this.onTap, super.key});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        width: 46,
        height: 46,
        decoration: BoxDecoration(
          color: BalanceColors.paper,
          border: Border.all(color: BalanceColors.ink, width: 2.5),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, size: 30),
      ),
    );
  }
}

class _Ruler extends StatelessWidget {
  const _Ruler({
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final labels = List.generate(
      5,
      (index) => min + ((max - min) ~/ 4) * index,
    );
    return Column(
      children: [
        SliderTheme(
          data: SliderTheme.of(context).copyWith(
            activeTrackColor: BalanceColors.ink,
            inactiveTrackColor: BalanceColors.ink,
            trackHeight: 1.5,
            activeTickMarkColor: BalanceColors.ink,
            inactiveTickMarkColor: BalanceColors.ink,
            thumbColor: BalanceColors.blue,
            thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 7),
            tickMarkShape: const RoundSliderTickMarkShape(tickMarkRadius: 2),
            overlayShape: const RoundSliderOverlayShape(overlayRadius: 14),
          ),
          child: Slider(
            value: value.clamp(min, max).toDouble(),
            min: min.toDouble(),
            max: max.toDouble(),
            divisions: 8,
            onChanged: (next) => onChanged(next.round()),
          ),
        ),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            for (final label in labels)
              Text(
                '$label',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
          ],
        ),
      ],
    );
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
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        height: 152,
        decoration: _raisedDecoration(
          color: selected ? BalanceColors.blue : BalanceColors.paper,
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(option.icon, size: 50, color: foreground),
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
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(13),
      child: Container(
        constraints: const BoxConstraints(minHeight: 86),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: _raisedDecoration(
          color: selected ? selectedColor : BalanceColors.paper,
        ),
        child: Row(
          children: [
            Icon(option.icon, size: 42),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    option.title,
                    style: Theme.of(
                      context,
                    ).textTheme.titleMedium?.copyWith(fontSize: 19),
                  ),
                  Text(
                    option.subtitle,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
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
    );
  }
}
