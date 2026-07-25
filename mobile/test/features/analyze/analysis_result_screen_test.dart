import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('result screen presents nutrition and estimated components', (
    tester,
  ) async {
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Cơm tấm sườn',
      'source': 'vision',
      'recognition_confidence': 0.86,
      'nutrition': {
        'total_calories': 650,
        'total_protein_g': 32,
        'total_fat_g': 22,
        'total_carbs_g': 78,
        'total_fiber_g': 4,
        'total_grams': 370,
        'confidence_score': 0.92,
        'catalog_coverage_score': 0.92,
        'items': [
          {
            'item_name': 'Cơm tấm',
            'grams': 200,
            'calories': 260,
            'protein_g': 5,
            'fat_g': 1,
            'carbs_g': 58,
            'fiber_g': 1,
            'found_in_db': true,
          },
          {
            'item_name': 'Sườn nướng',
            'grams': 120,
            'calories': 320,
            'protein_g': 25,
            'fat_g': 20,
            'carbs_g': 10,
            'fiber_g': 0,
            'found_in_db': true,
          },
        ],
      },
      'dishes': <Object>[],
    });

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalysisResultScreen(result: result),
      ),
    );

    expect(find.text('Kết quả phân tích'), findsOneWidget);
    expect(find.text('Cơm tấm sườn'), findsOneWidget);
    expect(find.text('650 kcal'), findsOneWidget);
    expect(find.textContaining('không thay thế tư vấn y tế'), findsOneWidget);
    expect(find.text('Nhận diện: 86%'), findsOneWidget);
    expect(find.text('Dữ liệu catalog: 92%'), findsOneWidget);
    expect(find.textContaining('Độ tin cậy:'), findsNothing);
    expect(find.text('Cơm tấm'), findsOneWidget);
    expect(find.text('Sườn nướng'), findsOneWidget);

    await tester.ensureVisible(find.text('Thêm vào nhật ký'));
    await tester.tap(find.text('Thêm vào nhật ký'));
    await tester.pump();
    expect(find.text('Đã thêm bữa ăn vào nhật ký'), findsOneWidget);
  });

  testWidgets('editing portion scales nutrition before saving', (tester) async {
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Phở bò',
      'source': 'vision',
      'nutrition': {
        'total_calories': 400,
        'total_protein_g': 20,
        'total_fat_g': 10,
        'total_carbs_g': 50,
        'total_fiber_g': 2,
        'total_grams': 400,
      },
      'dishes': <Object>[],
    });

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalysisResultScreen(result: result),
      ),
    );
    await tester.ensureVisible(find.text('Chỉnh sửa'));
    await tester.tap(find.text('Chỉnh sửa'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('portion-grams')), '200');
    await tester.tap(find.text('Áp dụng'));
    await tester.pumpAndSettle();

    expect(find.text('200 kcal'), findsOneWidget);
    expect(find.text('10 g'), findsOneWidget);
  });
}
