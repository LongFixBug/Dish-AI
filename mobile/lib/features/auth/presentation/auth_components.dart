import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
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
    return Scaffold(
      body: GraphPaperBackground(
        child: SafeArea(
          child: Stack(
            children: [
              Positioned.fill(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(24, 64, 24, 32),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 460),
                      child: child,
                    ),
                  ),
                ),
              ),
              if (showBackButton)
                Positioned(
                  left: 16,
                  top: 8,
                  child: IconButton.filled(
                    onPressed: () => Navigator.of(context).pop(),
                    style: IconButton.styleFrom(
                      backgroundColor: BalanceColors.paper,
                      foregroundColor: BalanceColors.ink,
                      side: const BorderSide(
                        color: BalanceColors.ink,
                        width: 2,
                      ),
                    ),
                    icon: const Icon(Icons.arrow_back_rounded),
                  ),
                ),
            ],
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
