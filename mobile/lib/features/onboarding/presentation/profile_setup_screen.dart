import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/dashboard/presentation/dashboard_screen.dart';
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
  String _gender = 'Nam';
  String _activity = 'Vừa phải';
  String _goal = 'Giảm cân';
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
    _gender = profile.gender;
    _activity = profile.activity;
    _goal = profile.goal;
  }

  void _changeInt(ValueSetter<int> setter, int value, int min, int max) {
    setState(() => setter(value.clamp(min, max)));
  }

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
            gender: _gender,
            activity: _activity,
            goal: _goal,
          ),
        );
      }
      if (!mounted) return;
      await Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute<void>(builder: (_) => const DashboardScreen()),
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
    return Scaffold(
      backgroundColor: BalanceColors.paper,
      body: SafeArea(
        child: Column(
          children: [
            OnboardingProgressHeader(
              step: _step,
              totalSteps: 4,
              onBack: _goBack,
            ),
            Expanded(
              child: SingleChildScrollView(
                key: ValueKey(_step),
                padding: const EdgeInsets.fromLTRB(24, 14, 24, 24),
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 180),
                  child: _buildStep(),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 22),
              child: PressableButton(
                label: _saving
                    ? 'Đang lưu...'
                    : _step == 3
                    ? 'Hoàn tất'
                    : 'Tiếp tục',
                backgroundColor: _step == 3
                    ? BalanceColors.yellow
                    : BalanceColors.blue,
                foregroundColor: _step == 3 ? BalanceColors.ink : Colors.white,
                onPressed: _saving ? null : _continue,
              ),
            ),
          ],
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
        targetWeight: _targetWeight,
        onSelected: (value) => setState(() => _goal = value),
        onWeightChanged: (value) =>
            _changeInt((next) => _targetWeight = next, value, 35, 180),
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
          min: 150,
          max: 190,
          onDecrement: () => onHeightChanged(height - 1),
          onIncrement: () => onHeightChanged(height + 1),
          onSliderChanged: onHeightChanged,
        ),
        const SizedBox(height: 24),
        NumberStepperCard(
          label: 'Cân nặng',
          value: weight,
          unit: 'kg',
          min: 45,
          max: 85,
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
    required this.targetWeight,
    required this.onSelected,
    required this.onWeightChanged,
  });

  final String selected;
  final int targetWeight;
  final ValueChanged<String> onSelected;
  final ValueChanged<int> onWeightChanged;

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
              'Giảm cân',
              'Giảm mỡ, thon gọn cơ thể.',
              Icons.south_rounded,
            ),
            ChoiceOption(
              'Giữ cân',
              'Duy trì cân nặng hiện tại.',
              Icons.gps_fixed_rounded,
            ),
            ChoiceOption(
              'Tăng cân',
              'Tăng cân khỏe mạnh, phát triển cơ bắp.',
              Icons.north_rounded,
            ),
          ],
          selected: selected,
          selectedColor: BalanceColors.orange,
          onSelected: onSelected,
        ),
        const SizedBox(height: 20),
        NumberStepperCard(
          label: 'Cân nặng mục tiêu',
          value: targetWeight,
          unit: 'kg',
          onDecrement: () => onWeightChanged(targetWeight - 1),
          onIncrement: () => onWeightChanged(targetWeight + 1),
        ),
      ],
    );
  }
}
