import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:flutter/material.dart';

class AuthPageShell extends StatelessWidget {
  const AuthPageShell({
    required this.child,
    this.showBackButton = true,
    super.key,
  });

  final Widget child;
  final bool showBackButton;

  @override
  Widget build(BuildContext context) {
    return BalanceScreenMotion(
      child: Scaffold(
        body: GraphPaperBackground(
          child: SafeArea(
            child: Stack(
              children: [
                Positioned.fill(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(24, 76, 24, 32),
                    child: Center(
                      child: ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 460),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const BalanceReveal(
                              index: 0,
                              child: AuthBrandMark(),
                            ),
                            const SizedBox(height: 18),
                            BalanceReveal(
                              index: 1,
                              child: SketchCard(
                                radius: 22,
                                padding: const EdgeInsets.fromLTRB(
                                  20,
                                  24,
                                  20,
                                  20,
                                ),
                                child: child,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                if (showBackButton)
                  Positioned(left: 8, top: 8, child: const BalanceBackButton()),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class AuthBrandMark extends StatelessWidget {
  const AuthBrandMark({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        SketchCard(
          padding: const EdgeInsets.all(4),
          radius: 14,
          shadow: false,
          child: Image.asset(
            'assets/branding/mascot.png',
            width: 44,
            height: 44,
            semanticLabel: 'Linh vật Balance',
          ),
        ),
        const SizedBox(width: 10),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'balance',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontSize: 28),
            ),
            const Text(
              'Ăn hiểu mình, sống cân bằng',
              style: TextStyle(
                color: Color(0xFF667085),
                fontSize: 13,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class AuthEyebrow extends StatelessWidget {
  const AuthEyebrow({required this.label, required this.icon, super.key});

  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: SketchCard(
        color: const Color(0xFFDCEBFA),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        radius: 99,
        shadow: false,
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16),
            const SizedBox(width: 6),
            Text(
              label,
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
    );
  }
}

class AuthGoogleButton extends StatelessWidget {
  const AuthGoogleButton({
    required this.label,
    required this.onPressed,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;
    return Opacity(
      opacity: enabled ? 1 : 0.55,
      child: Semantics(
        button: true,
        enabled: enabled,
        label: label,
        child: SketchCard(
          padding: EdgeInsets.zero,
          radius: 12,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: onPressed,
              borderRadius: BorderRadius.circular(10),
              child: SizedBox(
                height: 54,
                width: double.infinity,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.account_circle_outlined, size: 25),
                    const SizedBox(width: 10),
                    Flexible(
                      child: Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
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

class LabeledTextField extends StatelessWidget {
  const LabeledTextField({
    required this.label,
    required this.hint,
    this.obscureText = false,
    this.keyboardType,
    this.prefixIcon,
    this.controller,
    this.validator,
    this.textInputAction,
    super.key,
  });

  final String label;
  final String hint;
  final bool obscureText;
  final TextInputType? keyboardType;
  final IconData? prefixIcon;
  final TextEditingController? controller;
  final FormFieldValidator<String>? validator;
  final TextInputAction? textInputAction;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          obscureText: obscureText,
          keyboardType: keyboardType,
          validator: validator,
          textInputAction: textInputAction,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          decoration: InputDecoration(
            hintText: hint,
            prefixIcon: prefixIcon == null ? null : Icon(prefixIcon),
          ),
        ),
      ],
    );
  }
}
