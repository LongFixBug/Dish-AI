import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_bottom_bar.dart';
import 'package:balance/core/widgets/fade_indexed_stack.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/features/dashboard/presentation/dashboard_screen.dart';
import 'package:balance/features/profile/presentation/profile_screen.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('thanh điều hướng không bị dựng lại khi đổi tab', (tester) async {
    // Yêu cầu cốt lõi: bấm icon chỉ đổi phần nội dung phía trên, thanh dưới
    // đứng yên. So sánh Element chứ không so widget: Element mới đồng nghĩa
    // với việc Flutter đã vứt thanh cũ đi và dựng lại từ đầu.
    await tester.pumpWidget(_testApp());
    final before = tester.element(find.byType(BalanceBottomBar));

    await tester.tap(find.text('Gợi ý'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Tôi'));
    await tester.pumpAndSettle();

    expect(tester.element(find.byType(BalanceBottomBar)), same(before));
    expect(find.byType(BalanceBottomBar), findsOneWidget);
  });

  testWidgets('mỗi tab giữ nguyên nội dung của mình khi quay lại', (
    tester,
  ) async {
    await tester.pumpWidget(_testApp());

    // Tab không được chọn vẫn nằm trong cây widget để giữ vị trí cuộn, nhưng
    // phải Offstage sau khi fade xong để nội dung ẩn không chồng lên UI.
    expect(find.byType(DashboardScreen), findsOneWidget);
    expect(find.byType(FadeIndexedStack), findsOneWidget);
    expect(find.byType(SuggestionsScreen, skipOffstage: false), findsOneWidget);
    expect(find.byType(ProfileScreen, skipOffstage: false), findsOneWidget);
    expect(
      tester
          .widget<Offstage>(
            find.descendant(
              of: find.byKey(const ValueKey('fade-stack-child-2')),
              matching: find.byType(Offstage),
            ),
          )
          .offstage,
      isTrue,
    );
  });

  testWidgets('tab đang mở được tô đậm trên thanh điều hướng', (tester) async {
    await tester.pumpWidget(_testApp());
    expect(
      tester
          .widget<BalanceBottomBar>(find.byType(BalanceBottomBar))
          .currentIndex,
      0,
    );

    await tester.tap(find.text('Nhật ký'));
    await tester.pumpAndSettle();

    expect(
      tester
          .widget<BalanceBottomBar>(find.byType(BalanceBottomBar))
          .currentIndex,
      1,
    );
  });
}

Widget _testApp() {
  // IndexedStack dựng cả bốn tab ngay từ đầu, nên ProfileScreen cần AppScope
  // có sẵn — khác với trước đây khi nó chỉ được dựng lúc điều hướng tới.
  return AppScope(
    notifier: AppState.memory(),
    child: MaterialApp(theme: BalanceTheme.light, home: const MainShell()),
  );
}
