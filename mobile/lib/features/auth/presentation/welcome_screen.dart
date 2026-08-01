import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/auth/presentation/login_screen.dart';
import 'package:balance/features/auth/presentation/sign_up_screen.dart';
import 'package:flutter/material.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  void _open(BuildContext context, Widget page) {
    Navigator.of(context).push(BalancePageRoute<void>(builder: (_) => page));
  }

  @override
  Widget build(BuildContext context) {
    return BalanceScreenMotion(
      child: Scaffold(
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
                      BalanceReveal(
                        index: 0,
                        child: SketchCard(
                          padding: EdgeInsets.zero,
                          radius: 26,
                          shadow: false,
                          child: Image.asset(
                            'assets/branding/balance-brand-board.png',
                            height: 190,
                            width: double.infinity,
                            fit: BoxFit.cover,
                            semanticLabel:
                                'Balance giúp bạn cân bằng dinh dưỡng',
                          ),
                        ),
                      ),
                      const SizedBox(height: 22),
                      BalanceReveal(
                        index: 1,
                        child: Column(
                          children: [
                            Text(
                              'balance',
                              style: Theme.of(
                                context,
                              ).textTheme.displaySmall?.copyWith(fontSize: 46),
                            ),
                            const SizedBox(height: 6),
                            Text(
                              'Hiểu món ăn. Hiểu cơ thể.',
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.bodyLarge,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      BalanceReveal(
                        index: 2,
                        child: Column(
                          children: [
                            SketchCard(
                              color: BalanceColors.green,
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 7,
                              ),
                              radius: 99,
                              shadow: false,
                              child: const Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.auto_awesome_rounded, size: 18),
                                  SizedBox(width: 6),
                                  Text(
                                    'AI nhận diện món Việt',
                                    style: TextStyle(
                                      color: BalanceColors.ink,
                                      fontSize: 14,
                                      fontWeight: FontWeight.w900,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 10),
                            const Text(
                              'Từ ảnh món ăn đến nhật ký của bạn',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: BalanceColors.muted,
                                fontSize: 15,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 26),
                      BalanceReveal(
                        index: 3,
                        child: Column(
                          children: [
                            PressableButton(
                              label: 'Bắt đầu',
                              icon: Icons.auto_awesome_rounded,
                              onPressed: () =>
                                  _open(context, const SignUpScreen()),
                            ),
                            const SizedBox(height: 14),
                            PressableButton(
                              label: 'Tôi đã có tài khoản',
                              backgroundColor: BalanceColors.paper,
                              foregroundColor: BalanceColors.ink,
                              onPressed: () =>
                                  _open(context, const LoginScreen()),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
