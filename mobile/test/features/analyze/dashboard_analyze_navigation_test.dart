import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/dashboard/presentation/dashboard_screen.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('dashboard camera action opens the backend analysis flow', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(theme: BalanceTheme.light, home: const DashboardScreen()),
    );

    final cameraButton = find.widgetWithText(PressableButton, 'Chụp món ăn');
    await tester.ensureVisible(cameraButton);
    await tester.tap(cameraButton);
    await tester.pumpAndSettle();

    expect(find.byType(AnalyzeScreen), findsOneWidget);
    expect(find.text('Chụp món ăn'), findsOneWidget);
    expect(find.text('Chọn ảnh từ thư viện'), findsOneWidget);
  });

  testWidgets('dashboard matches the complete home information hierarchy', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(theme: BalanceTheme.light, home: const DashboardScreen()),
    );

    expect(find.text('Chào buổi sáng, An!'), findsOneWidget);
    expect(find.text('1.240'), findsOneWidget);
    expect(find.text('/ 1.800 kcal'), findsOneWidget);
    expect(find.text('Bữa sáng'), findsOneWidget);
    expect(find.text('Bữa trưa'), findsOneWidget);
    expect(find.text('Bữa tối'), findsOneWidget);
  });

  testWidgets('suggestion tab opens the dinner recommendation screen', (
    tester,
  ) async {
    // Tab nằm trên MainShell chứ không còn trong từng màn hình.
    await tester.pumpWidget(
      AppScope(
        notifier: AppState.memory(),
        child: MaterialApp(theme: BalanceTheme.light, home: const MainShell()),
      ),
    );

    await tester.tap(find.text('Gợi ý'));
    await tester.pumpAndSettle();

    expect(find.byType(SuggestionsScreen), findsOneWidget);
    // Món gợi ý nay do backend trả về, không còn là chữ cứng trong code —
    // ở đây chỉ cần chốt là đã sang đúng tab.
    expect(find.text('Gợi ý cho bạn'), findsOneWidget);
  });
}
