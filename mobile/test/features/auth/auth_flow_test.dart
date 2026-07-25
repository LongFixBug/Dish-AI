import 'package:balance/app.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

Future<BalanceApp> authenticatedTestApp() async {
  final state = await AppState.restore(
    MemoryAppStorage(),
    authGateway: FakeAuthGateway(),
  );
  return BalanceApp(appState: state);
}

void main() {
  testWidgets('existing user can open the login screen', (tester) async {
    await tester.pumpWidget(await authenticatedTestApp());

    expect(find.text('balance'), findsOneWidget);
    expect(find.text('Hiểu món ăn. Hiểu cơ thể.'), findsOneWidget);

    await tester.tap(find.text('Tôi đã có tài khoản'));
    await tester.pumpAndSettle();

    expect(find.text('Đăng nhập'), findsWidgets);
    expect(find.text('Email'), findsOneWidget);
    expect(find.text('Mật khẩu'), findsOneWidget);
    expect(find.text('Đăng nhập với Google'), findsNothing);
    expect(find.text('Quên mật khẩu?'), findsNothing);
  });

  testWidgets('new user can move from login to sign up', (tester) async {
    await tester.pumpWidget(await authenticatedTestApp());

    await tester.tap(find.text('Tôi đã có tài khoản'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('Đăng ký'));
    await tester.tap(find.text('Đăng ký'));
    await tester.pumpAndSettle();

    expect(find.text('Tạo tài khoản'), findsWidgets);
    expect(find.text('Họ và tên'), findsOneWidget);
    expect(find.text('Tôi đồng ý với Chính sách bảo mật'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('privacy-policy-link')));
    await tester.pumpAndSettle();
    expect(find.text('Chính sách bảo mật'), findsOneWidget);
    expect(find.textContaining('đồng ý riêng'), findsOneWidget);
  });

  testWidgets('login continues through profile setup to dashboard', (
    tester,
  ) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await tester.pumpWidget(BalanceApp(appState: state));

    await tester.tap(find.text('Tôi đã có tài khoản'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(
      find.widgetWithText(PressableButton, 'Đăng nhập'),
    );
    await tester.enterText(
      find.byKey(const ValueKey('login-email')),
      'an@example.com',
    );
    await tester.enterText(
      find.byKey(const ValueKey('login-password')),
      'matkhau123',
    );
    await tester.tap(find.widgetWithText(PressableButton, 'Đăng nhập'));
    await tester.pumpAndSettle();

    expect(find.text('Cho Balance\nbiết về bạn'), findsOneWidget);
    expect(find.text('1 / 4'), findsOneWidget);
    expect(find.text('Tuổi'), findsOneWidget);
    expect(find.text('24 tuổi'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('age-increment')));
    await tester.pump();
    expect(find.text('25 tuổi'), findsOneWidget);

    await tester.ensureVisible(find.text('Tiếp tục'));
    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();
    expect(find.text('Chỉ số cơ thể'), findsOneWidget);
    expect(find.text('2 / 4'), findsOneWidget);
    expect(find.text('170 cm'), findsOneWidget);
    expect(find.text('65 kg'), findsOneWidget);

    await tester.ensureVisible(find.text('Tiếp tục'));
    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();
    expect(find.text('Bạn vận động thế nào?'), findsOneWidget);
    expect(find.text('3 / 4'), findsOneWidget);

    await tester.tap(find.text('Vừa phải'));
    await tester.ensureVisible(find.text('Tiếp tục'));
    await tester.tap(find.text('Tiếp tục'));
    await tester.pumpAndSettle();
    expect(find.text('Mục tiêu của bạn'), findsOneWidget);
    expect(find.text('4 / 4'), findsOneWidget);

    await tester.tap(find.text('Giảm cân'));
    await tester.enterText(
      find.byKey(const ValueKey('profile-allergies')),
      'Hải sản, đậu phộng',
    );
    await tester.enterText(
      find.byKey(const ValueKey('profile-medical-conditions')),
      'Tăng huyết áp',
    );
    await tester.ensureVisible(find.text('Hoàn tất'));
    await tester.tap(find.text('Hoàn tất'));
    await tester.pumpAndSettle();

    expect(find.text('Hôm nay'), findsOneWidget);
    expect(find.text('0'), findsOneWidget);
    expect(find.text('Trang chủ'), findsOneWidget);
    expect(find.text('Nhật ký'), findsOneWidget);
    expect(find.text('Gợi ý'), findsOneWidget);
    expect(find.text('Tôi'), findsOneWidget);
    expect(state.profile?.allergies, ['Hải sản', 'đậu phộng']);
    expect(state.profile?.medicalConditions, ['Tăng huyết áp']);
  });

  testWidgets('accepted sign up continues to profile setup', (tester) async {
    await tester.pumpWidget(await authenticatedTestApp());

    await tester.tap(find.text('Bắt đầu'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('signup-name')),
      'Nguyễn Văn An',
    );
    await tester.enterText(
      find.byKey(const ValueKey('signup-email')),
      'an@example.com',
    );
    await tester.enterText(
      find.byKey(const ValueKey('signup-password')),
      'matkhau123',
    );
    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    await tester.ensureVisible(
      find.widgetWithText(PressableButton, 'Tạo tài khoản'),
    );
    await tester.tap(find.widgetWithText(PressableButton, 'Tạo tài khoản'));
    await tester.pumpAndSettle();

    expect(find.text('Cho Balance\nbiết về bạn'), findsOneWidget);
  });
}
