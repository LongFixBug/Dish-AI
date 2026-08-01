import 'package:balance/app.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
  testWidgets('profile tab shows saved data and can sign out', (tester) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await state.signIn(email: _profile.email, password: 'matkhau123');
    await state.completeProfile(_profile);
    await tester.pumpWidget(BalanceApp(appState: state));

    await tester.tap(find.text('Tôi'));
    await tester.pumpAndSettle();
    expect(find.text('An'), findsOneWidget);
    expect(find.text('an@example.com'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('Đăng xuất'),
      180,
      scrollable: find.byType(Scrollable).last,
    );
    await tester.drag(find.byType(ListView), const Offset(0, -80));
    await tester.pumpAndSettle();
    expect(find.text('Đăng xuất'), findsOneWidget);
    expect(find.byType(PressableButton), findsNWidgets(2));
    expect(find.byType(OutlinedButton), findsNothing);

    await tester.tap(find.text('Đăng xuất'));
    await tester.pumpAndSettle();
    expect(find.text('Hiểu món ăn. Hiểu cơ thể.'), findsOneWidget);
    expect(state.isSignedIn, isFalse);
  });
}

const _profile = UserProfile(
  name: 'An',
  email: 'an@example.com',
  age: 25,
  heightCm: 170,
  weightKg: 65,
  targetWeightKg: 60,
  gender: 'Nam',
  activity: 'Vừa phải',
  goal: 'Giảm cân',
);
