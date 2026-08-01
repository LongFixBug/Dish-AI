import 'package:balance/app.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
  testWidgets('login blocks empty and malformed credentials', (tester) async {
    await tester.pumpWidget(const BalanceApp());
    await tester.tap(find.text('Tôi đã có tài khoản'));
    await tester.pumpAndSettle();

    await tester.ensureVisible(
      find.widgetWithText(PressableButton, 'Đăng nhập'),
    );
    await tester.tap(find.widgetWithText(PressableButton, 'Đăng nhập'));
    await tester.pump();
    expect(find.text('Vui lòng nhập email'), findsOneWidget);
    expect(find.text('Vui lòng nhập mật khẩu'), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('login-email')), 'abc');
    await tester.enterText(find.byKey(const ValueKey('login-password')), '123');
    await tester.ensureVisible(
      find.widgetWithText(PressableButton, 'Đăng nhập'),
    );
    await tester.tap(find.widgetWithText(PressableButton, 'Đăng nhập'));
    await tester.pump();
    expect(find.text('Email chưa đúng định dạng'), findsOneWidget);
    expect(find.text('Mật khẩu cần ít nhất 8 ký tự'), findsOneWidget);
  });

  testWidgets('valid credentials open profile setup', (tester) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await tester.pumpWidget(BalanceApp(appState: state));
    await tester.tap(find.text('Tôi đã có tài khoản'));
    await tester.pumpAndSettle();

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
  });
}
