import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/auth/presentation/auth_components.dart';
import 'package:balance/features/auth/presentation/sign_up_screen.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _submitting = false;
  bool _googleSubmitting = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting || !_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);
    try {
      final state = AppScope.of(context);
      await state.signIn(
        email: _emailController.text,
        password: _passwordController.text,
      );
      if (!mounted) return;
      final nextPage = state.profile == null
          ? const ProfileSetupScreen()
          : const MainShell();
      await Navigator.of(context).pushAndRemoveUntil(
        BalancePageRoute<void>(builder: (_) => nextPage),
        (_) => false,
      );
    } on Object catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _submitGoogle() async {
    if (_submitting || _googleSubmitting) return;
    setState(() => _googleSubmitting = true);
    try {
      final state = AppScope.of(context);
      await state.signInWithGoogle();
      if (!mounted) return;
      final nextPage = state.profile == null
          ? const ProfileSetupScreen()
          : const MainShell();
      await Navigator.of(context).pushAndRemoveUntil(
        BalancePageRoute<void>(builder: (_) => nextPage),
        (_) => false,
      );
    } on Object catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => _googleSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthPageShell(
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const AuthEyebrow(
              label: 'CHÀO MỪNG TRỞ LẠI',
              icon: Icons.waving_hand_rounded,
            ),
            const SizedBox(height: 18),
            Text('Đăng nhập', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 12),
            Text(
              'Chào mừng bạn quay lại với Balance.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 28),
            LabeledTextField(
              key: const ValueKey('login-email'),
              controller: _emailController,
              label: 'Email',
              hint: 'nhap@email.com',
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              prefixIcon: Icons.email_outlined,
              validator: _validateEmail,
            ),
            const SizedBox(height: 20),
            LabeledTextField(
              key: const ValueKey('login-password'),
              controller: _passwordController,
              label: 'Mật khẩu',
              hint: 'Nhập mật khẩu',
              obscureText: true,
              textInputAction: TextInputAction.done,
              prefixIcon: Icons.lock_outline_rounded,
              validator: _validatePassword,
            ),
            const SizedBox(height: 20),
            PressableButton(
              label: _submitting ? 'Đang đăng nhập...' : 'Đăng nhập',
              onPressed: _submitting || _googleSubmitting ? null : _submit,
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                const Expanded(child: Divider()),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text(
                    'hoặc',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
                const Expanded(child: Divider()),
              ],
            ),
            const SizedBox(height: 18),
            AuthGoogleButton(
              key: const ValueKey('login-google'),
              onPressed: _submitting || _googleSubmitting
                  ? null
                  : _submitGoogle,
              label: _googleSubmitting
                  ? 'Đang kết nối Google...'
                  : 'Tiếp tục với Google',
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('Chưa có tài khoản?'),
                TextButton(
                  onPressed: () => Navigator.of(context).pushReplacement(
                    BalancePageRoute<void>(
                      builder: (_) => const SignUpScreen(),
                    ),
                  ),
                  child: const Text('Đăng ký'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

String? _validateEmail(String? raw) {
  final value = raw?.trim() ?? '';
  if (value.isEmpty) return 'Vui lòng nhập email';
  if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(value)) {
    return 'Email chưa đúng định dạng';
  }
  return null;
}

String? _validatePassword(String? value) {
  if (value == null || value.isEmpty) return 'Vui lòng nhập mật khẩu';
  if (value.length < 8) return 'Mật khẩu cần ít nhất 8 ký tự';
  return null;
}
