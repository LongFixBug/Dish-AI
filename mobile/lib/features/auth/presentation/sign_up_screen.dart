import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/auth/presentation/auth_components.dart';
import 'package:balance/features/auth/presentation/login_screen.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';

class SignUpScreen extends StatefulWidget {
  const SignUpScreen({super.key});

  @override
  State<SignUpScreen> createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _acceptedPolicy = false;
  bool _submitting = false;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting || !_acceptedPolicy || !_formKey.currentState!.validate()) {
      return;
    }
    setState(() => _submitting = true);
    try {
      await AppScope.of(context).signUp(
        email: _emailController.text,
        password: _passwordController.text,
        displayName: _nameController.text,
      );
      if (!mounted) return;
      await Navigator.of(context).pushAndRemoveUntil(
        BalancePageRoute<void>(builder: (_) => const ProfileSetupScreen()),
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

  @override
  Widget build(BuildContext context) {
    return AuthPageShell(
      child: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const AuthEyebrow(
              label: 'BẮT ĐẦU HÔM NAY',
              icon: Icons.auto_awesome_rounded,
            ),
            const SizedBox(height: 18),
            Text(
              'Tạo tài khoản',
              style: Theme.of(context).textTheme.displaySmall,
            ),
            const SizedBox(height: 12),
            Text(
              'Bắt đầu hành trình cân bằng theo cách của bạn.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 28),
            LabeledTextField(
              key: const ValueKey('signup-name'),
              controller: _nameController,
              label: 'Họ và tên',
              hint: 'Nguyễn Văn An',
              prefixIcon: Icons.person_outline_rounded,
              validator: (value) => value == null || value.trim().length < 2
                  ? 'Vui lòng nhập họ tên'
                  : null,
            ),
            const SizedBox(height: 20),
            LabeledTextField(
              key: const ValueKey('signup-email'),
              controller: _emailController,
              label: 'Email',
              hint: 'nhap@email.com',
              keyboardType: TextInputType.emailAddress,
              prefixIcon: Icons.email_outlined,
              validator: _validateEmail,
            ),
            const SizedBox(height: 20),
            LabeledTextField(
              key: const ValueKey('signup-password'),
              controller: _passwordController,
              label: 'Mật khẩu',
              hint: 'Tối thiểu 8 ký tự',
              obscureText: true,
              prefixIcon: Icons.lock_outline_rounded,
              validator: _validatePassword,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Checkbox(
                  value: _acceptedPolicy,
                  activeColor: BalanceColors.blue,
                  onChanged: (value) {
                    setState(() => _acceptedPolicy = value ?? false);
                  },
                ),
                Expanded(
                  child: TextButton(
                    key: const ValueKey('privacy-policy-link'),
                    onPressed: () => _showPrivacyPolicy(context),
                    style: TextButton.styleFrom(
                      alignment: Alignment.centerLeft,
                      padding: const EdgeInsets.symmetric(horizontal: 4),
                    ),
                    child: const Text('Tôi đồng ý với Chính sách bảo mật'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            PressableButton(
              label: _submitting ? 'Đang tạo...' : 'Tạo tài khoản',
              backgroundColor: BalanceColors.yellow,
              foregroundColor: BalanceColors.ink,
              onPressed: _acceptedPolicy && !_submitting ? _submit : null,
            ),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text('Đã có tài khoản?'),
                TextButton(
                  onPressed: () => Navigator.of(context).pushReplacement(
                    BalancePageRoute<void>(builder: (_) => const LoginScreen()),
                  ),
                  child: const Text('Đăng nhập'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

Future<void> _showPrivacyPolicy(BuildContext context) {
  return showDialog<void>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Chính sách bảo mật'),
      content: const SingleChildScrollView(
        child: Text(
          'Balance lưu thông tin tài khoản trên máy chủ và bảo vệ phiên đăng '
          'nhập trong vùng lưu trữ an toàn của thiết bị. Hồ sơ sức khỏe và '
          'nhật ký ăn uống được dùng để hiển thị trải nghiệm trong ứng dụng.\n\n'
          'Ảnh phân tích không được giữ lại sau khi xử lý. Ảnh chỉ được lưu '
          'làm dữ liệu cải thiện mô hình khi bạn đồng ý riêng tại bước gửi '
          'phản hồi; bạn có thể yêu cầu xóa phản hồi đã gửi.',
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Đã hiểu'),
        ),
      ],
    ),
  );
}

String? _validateEmail(String? raw) {
  final value = raw?.trim() ?? '';
  if (value.isEmpty) return 'Vui lòng nhập email';
  return RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(value)
      ? null
      : 'Email chưa đúng định dạng';
}

String? _validatePassword(String? value) {
  if (value == null || value.isEmpty) return 'Vui lòng nhập mật khẩu';
  return value.length < 8 ? 'Mật khẩu cần ít nhất 8 ký tự' : null;
}
