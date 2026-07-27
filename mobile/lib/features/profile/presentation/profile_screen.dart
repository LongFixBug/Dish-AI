import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/auth/presentation/welcome_screen.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final profile = state.profile;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hồ sơ'),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
      ),
      body: GraphPaperBackground(
        child: SafeArea(
          top: false,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
            children: [
              SketchCard(
                child: Column(
                  children: [
                    const CircleAvatar(
                      radius: 42,
                      backgroundColor: BalanceColors.yellow,
                      child: Icon(
                        Icons.person_rounded,
                        size: 48,
                        color: BalanceColors.ink,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      profile?.name ?? 'Bạn',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    Text(profile?.email ?? state.accountEmail),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (profile != null)
                SketchCard(
                  child: Column(
                    children: [
                      _ProfileRow('Tuổi', '${profile.age}'),
                      _ProfileRow('Chiều cao', '${profile.heightCm} cm'),
                      _ProfileRow('Cân nặng', '${profile.weightKg} kg'),
                      _ProfileRow('Mục tiêu', profile.goal),
                      _ProfileRow('Thời hạn', '${profile.targetDays} ngày'),
                      if (profile.allergies.isNotEmpty)
                        _ProfileRow('Dị ứng', profile.allergies.join(', ')),
                      if (profile.medicalConditions.isNotEmpty)
                        _ProfileRow(
                          'Bệnh nền',
                          profile.medicalConditions.join(', '),
                        ),
                      _ProfileRow(
                        'Mục tiêu ước tính',
                        '${profile.dailyCalorieTarget} kcal',
                      ),
                      _ProfileRow(
                        'Macro mục tiêu',
                        'Đạm ${profile.nutritionTarget.proteinTargetG.round()} g · '
                            'Carb ${profile.nutritionTarget.carbohydrateTargetG.round()} g · '
                            'Fat ${profile.nutritionTarget.fatTargetG.round()} g',
                        showDivider: false,
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Mức năng lượng dùng công thức Mifflin–St Jeor và chỉ '
                        'là ước tính; không phù hợp để tự điều trị, dùng cho '
                        'trẻ em, thai kỳ hoặc bệnh lý.',
                        style: TextStyle(fontSize: 12),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 18),
              PressableButton(
                label: 'Chỉnh sửa hồ sơ',
                icon: Icons.edit_outlined,
                backgroundColor: BalanceColors.yellow,
                foregroundColor: BalanceColors.ink,
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const ProfileSetupScreen(),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () => _signOut(context),
                icon: const Icon(Icons.logout_rounded),
                label: const Text('Đăng xuất'),
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(54),
                  foregroundColor: Colors.red.shade700,
                  side: BorderSide(color: Colors.red.shade700, width: 2),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _signOut(BuildContext context) async {
    final state = AppScope.of(context);
    await state.signOut();
    if (!context.mounted) return;
    await Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const WelcomeScreen()),
      (_) => false,
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow(this.label, this.value, {this.showDivider = true});

  final String label;
  final String value;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Row(
            children: [
              Expanded(child: Text(label)),
              Flexible(
                child: Text(
                  value,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.right,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
        ),
        if (showDivider) const Divider(height: 1),
      ],
    );
  }
}
