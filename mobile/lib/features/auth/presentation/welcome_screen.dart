import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/auth/presentation/login_screen.dart';
import 'package:balance/features/auth/presentation/sign_up_screen.dart';
import 'package:flutter/material.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  void _open(BuildContext context, Widget page) {
    Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: GraphPaperBackground(
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(32),
                      child: Image.asset(
                        'assets/branding/balance-app-icon.png',
                        height: 250,
                        width: 250,
                      ),
                    ),
                    const SizedBox(height: 24),
                    Text(
                      'balance',
                      style: Theme.of(
                        context,
                      ).textTheme.displaySmall?.copyWith(fontSize: 48),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Hiểu món ăn. Hiểu cơ thể.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 36),
                    PressableButton(
                      label: 'Bắt đầu',
                      icon: Icons.auto_awesome_rounded,
                      onPressed: () => _open(context, const SignUpScreen()),
                    ),
                    const SizedBox(height: 18),
                    PressableButton(
                      label: 'Tôi đã có tài khoản',
                      backgroundColor: BalanceColors.paper,
                      foregroundColor: BalanceColors.ink,
                      onPressed: () => _open(context, const LoginScreen()),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
