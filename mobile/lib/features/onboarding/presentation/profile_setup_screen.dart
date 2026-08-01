import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/features/onboarding/domain/goal_target_rules.dart';
import 'package:balance/features/onboarding/presentation/onboarding_widgets.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';

class ProfileSetupScreen extends StatefulWidget {
  const ProfileSetupScreen({super.key});

  @override
  State<ProfileSetupScreen> createState() => _ProfileSetupScreenState();
}

class _ProfileSetupScreenState extends State<ProfileSetupScreen> {
  int _step = 0;
  int _age = 24;
  int _height = 170;
  int _weight = 65;
  int _targetWeight = 60;
  int _targetDays = 90;
  String _gender = 'Nam';
  String _activity = 'Vừa phải';
  // Rỗng = chưa chọn: cân nặng mong muốn chỉ hiện ra sau khi có mục tiêu, vì
  // "muốn nặng bao nhiêu" chỉ có nghĩa khi đã biết đang muốn tăng hay giảm.
  String _goal = '';
  String _allergies = '';
  String _medicalConditions = '';
  bool _saving = false;
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_initialized) return;
    _initialized = true;
    final profile = AppScope.maybeOf(context)?.profile;
    if (profile == null) return;
    _age = profile.age;
    _height = profile.heightCm;
    _weight = profile.weightKg;
    _targetWeight = profile.targetWeightKg;
    _targetDays = profile.targetDays;
    _gender = profile.gender;
    _activity = profile.activity;
    _goal = profile.goal;
    _allergies = profile.allergies.join(', ');
    _medicalConditions = profile.medicalConditions.join(', ');
  }

  void _changeInt(ValueSetter<int> setter, int value, int min, int max) {
    setState(() => setter(value.clamp(min, max)));
  }

  /// Đổi mục tiêu thì kéo luôn cân nặng mong muốn về vùng hợp lý của mục tiêu
  /// đó, để thước không mở ra ở một con số mâu thuẫn sẵn.
  void _selectGoal(String goal) {
    setState(() {
      _goal = goal;
      final range = targetWeightRange(goal: goal, weightKg: _weight);
      final error = targetWeightError(
        goal: goal,
        weightKg: _weight,
        targetWeightKg: _targetWeight,
      );
      _targetWeight = error == null
          ? _targetWeight.clamp(range.min, range.max)
          : suggestedTargetWeight(goal: goal, weightKg: _weight);
    });
  }

  bool get _canContinue =>
      _step != 3 ||
      isGoalStepComplete(
        goal: _goal,
        weightKg: _weight,
        targetWeightKg: _targetWeight,
      );

  void _goBack() {
    if (_step == 0) {
      Navigator.of(context).pop();
      return;
    }
    setState(() => _step -= 1);
  }

  Future<void> _continue() async {
    if (_step < 3) {
      setState(() => _step += 1);
      return;
    }
    if (_saving) return;
    setState(() => _saving = true);
    try {
      final state = AppScope.maybeOf(context);
      if (state != null) {
        final email = state.accountEmail;
        final fallbackName = email.isEmpty
            ? 'Bạn'
            : email.split('@').first.replaceAll('.', ' ');
        await state.completeProfile(
          UserProfile(
            name: state.displayName.isEmpty ? fallbackName : state.displayName,
            email: email,
            age: _age,
            heightCm: _height,
            weightKg: _weight,
            targetWeightKg: _targetWeight,
            targetDays: _targetDays,
            gender: _gender,
            activity: _activity,
            goal: _goal,
            allergies: _commaSeparatedValues(_allergies),
            medicalConditions: _commaSeparatedValues(_medicalConditions),
          ),
        );
      }
      if (!mounted) return;
      await Navigator.of(context).pushAndRemoveUntil(
        BalancePageRoute<void>(builder: (_) => const MainShell()),
        (_) => false,
      );
    } on Object {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Không thể lưu hồ sơ. Hãy thử lại.')),
      );
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return BalanceScreenMotion(
      child: Scaffold(
        body: GraphPaperBackground(
          child: SafeArea(
            child: Column(
              children: [
                BalanceReveal(
                  index: 0,
                  child: OnboardingProgressHeader(
                    step: _step,
                    totalSteps: 4,
                    onBack: _goBack,
                  ),
                ),
                Expanded(
                  child: BalanceReveal(
                    index: 1,
                    child: SingleChildScrollView(
                      key: ValueKey(_step),
                      padding: const EdgeInsets.fromLTRB(24, 18, 24, 24),
                      child: Center(
                        child: ConstrainedBox(
                          constraints: const BoxConstraints(maxWidth: 520),
                          child: AnimatedSwitcher(
                            duration: const Duration(milliseconds: 220),
                            reverseDuration: const Duration(milliseconds: 160),
                            transitionBuilder: (child, animation) {
                              return FadeTransition(
                                opacity: animation,
                                child: SlideTransition(
                                  position:
                                      Tween<Offset>(
                                        begin: const Offset(0.02, 0),
                                        end: Offset.zero,
                                      ).animate(
                                        CurvedAnimation(
                                          parent: animation,
                                          curve: Curves.easeOutCubic,
                                        ),
                                      ),
                                  child: child,
                                ),
                              );
                            },
                            child: _buildStep(),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
                BalanceReveal(
                  index: 2,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 22),
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 520),
                      child: PressableButton(
                        label: _saving
                            ? 'Đang lưu...'
                            : _step == 3
                            ? 'Hoàn tất'
                            : 'Tiếp tục',
                        backgroundColor: _step == 3
                            ? BalanceColors.yellow
                            : BalanceColors.blue,
                        foregroundColor: _step == 3
                            ? BalanceColors.ink
                            : Colors.white,
                        onPressed: _saving || !_canContinue ? null : _continue,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStep() {
    return switch (_step) {
      0 => _AboutStep(
        age: _age,
        gender: _gender,
        onAgeChanged: (value) =>
            _changeInt((next) => _age = next, value, 13, 100),
        onGenderChanged: (value) => setState(() => _gender = value),
      ),
      1 => _BodyMetricsStep(
        height: _height,
        weight: _weight,
        onHeightChanged: (value) =>
            _changeInt((next) => _height = next, value, 120, 220),
        onWeightChanged: (value) =>
            _changeInt((next) => _weight = next, value, 35, 180),
      ),
      2 => _ActivityStep(
        selected: _activity,
        onSelected: (value) => setState(() => _activity = value),
      ),
      _ => _GoalStep(
        selected: _goal,
        currentWeight: _weight,
        targetWeight: _targetWeight,
        targetDays: _targetDays,
        onSelected: _selectGoal,
        onWeightChanged: (value) {
          final range = targetWeightRange(goal: _goal, weightKg: _weight);
          _changeInt(
            (next) => _targetWeight = next,
            value,
            range.min,
            range.max,
          );
        },
        onTargetDaysChanged: (value) => setState(() => _targetDays = value),
        allergies: _allergies,
        medicalConditions: _medicalConditions,
        onAllergiesChanged: (value) => _allergies = value,
        onMedicalConditionsChanged: (value) => _medicalConditions = value,
      ),
    };
  }
}

class _AboutStep extends StatelessWidget {
  const _AboutStep({
    required this.age,
    required this.gender,
    required this.onAgeChanged,
    required this.onGenderChanged,
  });

  final int age;
  final String gender;
  final ValueChanged<int> onAgeChanged;
  final ValueChanged<String> onGenderChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('about-step'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const OnboardingTitle(
          title: 'Cho Balance\nbiết về bạn',
          subtitle: 'Thông tin này giúp tính nhu cầu năng lượng phù hợp.',
        ),
        const SizedBox(height: 30),
        NumberStepperCard(
          label: 'Tuổi',
          value: age,
          unit: 'tuổi',
          decrementKey: const ValueKey('age-decrement'),
          incrementKey: const ValueKey('age-increment'),
          onDecrement: () => onAgeChanged(age - 1),
          onIncrement: () => onAgeChanged(age + 1),
        ),
        const SizedBox(height: 28),
        Text('Giới tính', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        Row(
          children: [
            for (final option in const [
              GenderOption('Nam', Icons.face_rounded),
              GenderOption('Nữ', Icons.face_3_rounded),
              GenderOption('Khác', Icons.person_outline_rounded),
            ])
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 10),
                  child: GenderCard(
                    option: option,
                    selected: gender == option.label,
                    onTap: () => onGenderChanged(option.label),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _BodyMetricsStep extends StatelessWidget {
  const _BodyMetricsStep({
    required this.height,
    required this.weight,
    required this.onHeightChanged,
    required this.onWeightChanged,
  });

  final int height;
  final int weight;
  final ValueChanged<int> onHeightChanged;
  final ValueChanged<int> onWeightChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('metrics-step'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const OnboardingTitle(
          title: 'Chỉ số cơ thể',
          subtitle: 'Nhập chiều cao và cân nặng để hỗ trợ theo dõi tốt hơn.',
        ),
        const SizedBox(height: 28),
        NumberStepperCard(
          label: 'Chiều cao',
          value: height,
          unit: 'cm',
          min: 120,
          max: 220,
          onDecrement: () => onHeightChanged(height - 1),
          onIncrement: () => onHeightChanged(height + 1),
          onSliderChanged: onHeightChanged,
        ),
        const SizedBox(height: 24),
        NumberStepperCard(
          label: 'Cân nặng',
          value: weight,
          unit: 'kg',
          min: 35,
          max: 180,
          onDecrement: () => onWeightChanged(weight - 1),
          onIncrement: () => onWeightChanged(weight + 1),
          onSliderChanged: onWeightChanged,
        ),
        const SizedBox(height: 22),
        const Center(
          child: Text(
            '⇄  Đổi đơn vị',
            style: TextStyle(
              color: BalanceColors.blueDark,
              decoration: TextDecoration.underline,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }
}

class _ActivityStep extends StatelessWidget {
  const _ActivityStep({required this.selected, required this.onSelected});

  final String selected;
  final ValueChanged<String> onSelected;

  @override
  Widget build(BuildContext context) {
    const options = [
      ChoiceOption(
        'Ít vận động',
        'Chủ yếu ngồi, ít hoặc không tập luyện.',
        Icons.weekend_outlined,
      ),
      ChoiceOption(
        'Nhẹ nhàng',
        'Hoạt động nhẹ, đi bộ, công việc nhẹ nhàng.',
        Icons.directions_walk_rounded,
      ),
      ChoiceOption(
        'Vừa phải',
        'Tập luyện 3–5 buổi/tuần, hoạt động vừa phải.',
        Icons.directions_run_rounded,
      ),
      ChoiceOption(
        'Năng động',
        'Tập luyện 6–7 buổi/tuần, hoạt động cường độ cao.',
        Icons.sports_gymnastics_rounded,
      ),
    ];
    return ChoiceList(
      key: const ValueKey('activity-step'),
      title: 'Bạn vận động thế nào?',
      subtitle: 'Chọn mức độ hoạt động hằng ngày phù hợp với bạn.',
      options: options,
      selected: selected,
      selectedColor: BalanceColors.green,
      onSelected: onSelected,
    );
  }
}

class _GoalStep extends StatelessWidget {
  const _GoalStep({
    required this.selected,
    required this.currentWeight,
    required this.targetWeight,
    required this.targetDays,
    required this.onSelected,
    required this.onWeightChanged,
    required this.onTargetDaysChanged,
    required this.allergies,
    required this.medicalConditions,
    required this.onAllergiesChanged,
    required this.onMedicalConditionsChanged,
  });

  final String selected;
  final int currentWeight;
  final int targetWeight;
  final int targetDays;
  final ValueChanged<String> onSelected;
  final ValueChanged<int> onWeightChanged;
  final ValueChanged<int> onTargetDaysChanged;
  final String allergies;
  final String medicalConditions;
  final ValueChanged<String> onAllergiesChanged;
  final ValueChanged<String> onMedicalConditionsChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('goal-step'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ChoiceList(
          title: 'Mục tiêu của bạn',
          subtitle: 'Chọn mục tiêu phù hợp để Balance đồng hành cùng bạn.',
          options: const [
            ChoiceOption(
              goalLose,
              'Giảm mỡ, thon gọn cơ thể.',
              Icons.south_rounded,
            ),
            ChoiceOption(
              goalMaintain,
              'Duy trì cân nặng hiện tại.',
              Icons.gps_fixed_rounded,
            ),
            ChoiceOption(
              goalGain,
              'Tăng cân khỏe mạnh, phát triển cơ bắp.',
              Icons.north_rounded,
            ),
          ],
          selected: selected,
          selectedColor: BalanceColors.orange,
          onSelected: onSelected,
        ),
        const SizedBox(height: 8),
        AnimatedSize(
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
          alignment: Alignment.topCenter,
          child: selected.isEmpty
              ? const _GoalHint()
              : _TargetWeightSection(
                  goal: selected,
                  currentWeight: currentWeight,
                  targetWeight: targetWeight,
                  onWeightChanged: onWeightChanged,
                ),
        ),
        const SizedBox(height: 24),
        DropdownButtonFormField<int>(
          key: const ValueKey('profile-target-days'),
          initialValue: targetDays,
          decoration: const InputDecoration(
            labelText: 'Thời hạn mục tiêu',
            helperText: 'Dùng để tính mức điều chỉnh calo theo từng ngày.',
          ),
          items: const [
            DropdownMenuItem(value: 30, child: Text('30 ngày')),
            DropdownMenuItem(value: 60, child: Text('60 ngày')),
            DropdownMenuItem(value: 90, child: Text('90 ngày')),
            DropdownMenuItem(value: 180, child: Text('180 ngày')),
          ],
          onChanged: (value) {
            if (value != null) onTargetDaysChanged(value);
          },
        ),
        const SizedBox(height: 24),
        TextFormField(
          key: const ValueKey('profile-allergies'),
          initialValue: allergies,
          maxLength: 300,
          decoration: const InputDecoration(
            labelText: 'Dị ứng thực phẩm (nếu có)',
            hintText: 'Ví dụ: hải sản, đậu phộng',
          ),
          onChanged: onAllergiesChanged,
        ),
        const SizedBox(height: 16),
        TextFormField(
          key: const ValueKey('profile-medical-conditions'),
          initialValue: medicalConditions,
          maxLength: 300,
          decoration: const InputDecoration(
            labelText: 'Bệnh nền liên quan dinh dưỡng (nếu có)',
            hintText: 'Ví dụ: tiểu đường, tăng huyết áp',
          ),
          onChanged: onMedicalConditionsChanged,
        ),
        const SizedBox(height: 12),
        const Text(
          'Balance chỉ dùng thông tin này để hiển thị cảnh báo an toàn; không '
          'thay thế chẩn đoán hoặc tư vấn y tế.',
          style: TextStyle(fontSize: 12),
        ),
      ],
    );
  }
}

class _GoalHint extends StatelessWidget {
  const _GoalHint();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      key: ValueKey('goal-hint'),
      padding: EdgeInsets.only(top: 4, bottom: 4),
      child: Text(
        'Chọn một mục tiêu để Balance hỏi tiếp cân nặng bạn mong muốn.',
        textAlign: TextAlign.center,
        style: TextStyle(color: BalanceColors.muted, fontSize: 15),
      ),
    );
  }
}

class _TargetWeightSection extends StatelessWidget {
  const _TargetWeightSection({
    required this.goal,
    required this.currentWeight,
    required this.targetWeight,
    required this.onWeightChanged,
  });

  final String goal;
  final int currentWeight;
  final int targetWeight;
  final ValueChanged<int> onWeightChanged;

  @override
  Widget build(BuildContext context) {
    if (goal == goalMaintain) {
      return Padding(
        key: const ValueKey('target-weight-maintain'),
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(
          'Balance sẽ giữ mốc $currentWeight kg hiện tại của bạn.',
          textAlign: TextAlign.center,
          style: const TextStyle(color: BalanceColors.muted, fontSize: 15),
        ),
      );
    }

    final range = targetWeightRange(goal: goal, weightKg: currentWeight);
    final error = targetWeightError(
      goal: goal,
      weightKg: currentWeight,
      targetWeightKg: targetWeight,
    );
    return Column(
      key: const ValueKey('target-weight-section'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 12),
        NumberStepperCard(
          label: 'Cân nặng mong muốn',
          value: targetWeight,
          unit: 'kg',
          min: range.min,
          max: range.max,
          onDecrement: () => onWeightChanged(targetWeight - 1),
          onIncrement: () => onWeightChanged(targetWeight + 1),
          onSliderChanged: onWeightChanged,
        ),
        const SizedBox(height: 10),
        Text(
          error ??
              (goal == goalGain
                  ? 'Bạn đang muốn tăng ${targetWeight - currentWeight} kg so '
                        'với $currentWeight kg hiện tại.'
                  : 'Bạn đang muốn giảm ${currentWeight - targetWeight} kg so '
                        'với $currentWeight kg hiện tại.'),
          style: TextStyle(
            fontSize: 14,
            fontWeight: error == null ? FontWeight.w500 : FontWeight.w700,
            color: error == null ? BalanceColors.muted : BalanceColors.orange,
          ),
        ),
      ],
    );
  }
}

List<String> _commaSeparatedValues(String raw) => raw
    .split(',')
    .map((value) => value.trim())
    .where((value) => value.isNotEmpty)
    .toList(growable: false);
