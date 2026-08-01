import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/auth/presentation/welcome_screen.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({this.animationSeed = 0, super.key});

  final int animationSeed;

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final profile = state.profile;
    return BalanceScreenMotion(
      seed: animationSeed,
      child: Scaffold(
        appBar: const BalanceAppBar(title: 'Hồ sơ'),
        body: GraphPaperBackground(
          child: SafeArea(
            top: false,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
              children: [
                BalanceReveal(
                  index: 0,
                  child: _ProfileIdentityCard(
                    name: profile?.name ?? 'Bạn',
                    email: profile?.email ?? state.accountEmail,
                  ),
                ),
                const SizedBox(height: 16),
                if (profile != null)
                  BalanceReveal(
                    index: 1,
                    child: _ProfileDetailsCard(profile: profile),
                  ),
                const SizedBox(height: 18),
                BalanceReveal(
                  index: 2,
                  child: PressableButton(
                    label: 'Chỉnh sửa hồ sơ',
                    icon: Icons.edit_outlined,
                    backgroundColor: BalanceColors.yellow,
                    foregroundColor: BalanceColors.ink,
                    onPressed: () => Navigator.of(context).push(
                      BalancePageRoute<void>(
                        builder: (_) => const ProfileSetupScreen(),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                BalanceReveal(
                  index: 3,
                  child: PressableButton(
                    label: 'Đăng xuất',
                    icon: Icons.logout_rounded,
                    backgroundColor: const Color(0xFFFFE4DE),
                    foregroundColor: const Color(0xFFC63E31),
                    onPressed: () => _signOut(context),
                  ),
                ),
              ],
            ),
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
      BalancePageRoute<void>(builder: (_) => const WelcomeScreen()),
      (_) => false,
    );
  }
}

class _ProfileIdentityCard extends StatelessWidget {
  const _ProfileIdentityCard({required this.name, required this.email});

  final String name;
  final String email;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: BalanceColors.paper,
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Container(
            width: 78,
            height: 78,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: BalanceColors.yellow,
              shape: BoxShape.circle,
              border: Border.all(color: BalanceColors.ink, width: 2.2),
              boxShadow: const [
                BoxShadow(color: BalanceColors.ink, offset: Offset(3, 4)),
              ],
            ),
            child: const Icon(
              Icons.person_rounded,
              size: 44,
              color: BalanceColors.ink,
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'HỒ SƠ CỦA BẠN',
                  style: TextStyle(
                    color: BalanceColors.blueDark,
                    fontSize: 12,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.6,
                  ),
                ),
                const SizedBox(height: 2),
                Text(name, style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 2),
                Text(email, style: Theme.of(context).textTheme.bodyMedium),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfileDetailsCard extends StatelessWidget {
  const _ProfileDetailsCard({required this.profile});

  final UserProfile profile;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const _ProfileSectionLabel(
            icon: Icons.auto_graph_rounded,
            label: 'Cơ thể & mục tiêu',
          ),
          const SizedBox(height: 8),
          _ProfileRow('Tuổi', '${profile.age}'),
          _ProfileRow('Chiều cao', '${profile.heightCm} cm'),
          _ProfileRow('Cân nặng', '${profile.weightKg} kg'),
          _ProfileRow('Mục tiêu', profile.goal),
          _ProfileRow('Thời hạn', '${profile.targetDays} ngày'),
          if (profile.allergies.isNotEmpty)
            _ProfileRow('Dị ứng', profile.allergies.join(', ')),
          if (profile.medicalConditions.isNotEmpty)
            _ProfileRow('Bệnh nền', profile.medicalConditions.join(', ')),
          _ProfileRow(
            'Mục tiêu ước tính',
            '${profile.dailyCalorieTarget} kcal',
            valueColor: BalanceColors.blueDark,
          ),
          _ProfileRow(
            'Macro mục tiêu',
            'Đạm ${profile.nutritionTarget.proteinTargetG.round()} g · '
                'Carb ${profile.nutritionTarget.carbohydrateTargetG.round()} g · '
                'Fat ${profile.nutritionTarget.fatTargetG.round()} g',
            showDivider: false,
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: BalanceColors.paperBlue,
              border: Border.all(color: BalanceColors.ink, width: 1.4),
              borderRadius: BorderRadius.circular(9),
            ),
            child: const Text(
              'Mức năng lượng dùng công thức Mifflin–St Jeor và chỉ là ước '
              'tính; không phù hợp để tự điều trị, dùng cho trẻ em, thai kỳ '
              'hoặc bệnh lý.',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProfileSectionLabel extends StatelessWidget {
  const _ProfileSectionLabel({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 34,
          height: 34,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: BalanceColors.green.withValues(alpha: 0.28),
            border: Border.all(color: BalanceColors.ink, width: 1.6),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, size: 20),
        ),
        const SizedBox(width: 9),
        Text(label, style: Theme.of(context).textTheme.titleMedium),
      ],
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow(
    this.label,
    this.value, {
    this.showDivider = true,
    this.valueColor = BalanceColors.ink,
  });

  final String label;
  final String value;
  final bool showDivider;
  final Color valueColor;

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
                  style: TextStyle(
                    color: valueColor,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
            ],
          ),
        ),
        if (showDivider)
          Container(
            height: 1,
            color: BalanceColors.ink.withValues(alpha: 0.16),
          ),
      ],
    );
  }
}
