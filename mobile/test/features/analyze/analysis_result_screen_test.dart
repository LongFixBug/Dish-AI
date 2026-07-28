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

  testWidgets(
    'component gram controls update calories and macros in real time',
    (tester) async {
      final result = AnalyzeResult.fromJson({
        'dish_name': 'Bánh mì thập cẩm',
        'source': 'vision',
        'nutrition': {
          'total_calories': 680,
          'total_protein_g': 30,
          'total_fat_g': 24,
          'total_carbs_g': 80,
          'total_fiber_g': 3,
          'total_grams': 200,
          'items': [
            {
              'item_name': 'Bánh mì thập cẩm',
              'grams': 200,
              'calories': 680,
              'protein_g': 30,
              'fat_g': 24,
              'carbs_g': 80,
              'fiber_g': 3,
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

      // Khối lượng chỉ sửa được sau khi bấm nút mở — chạm nhầm không còn bật
      // bàn phím giữa lúc đang cuộn xem kết quả.
      expect(find.byKey(const ValueKey('component-grams-0')), findsNothing);
      final toggle = find.byKey(const ValueKey('component-edit-toggle-0'));
      await tester.ensureVisible(toggle);
      await tester.pumpAndSettle();
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('component-grams-0')), findsOneWidget);
      expect(
        tester
            .widget<Text>(find.byKey(const ValueKey('component-calories-0')))
            .data,
        '680 kcal',
      );

      await tester.tap(find.byKey(const ValueKey('component-plus-0')));
      await tester.pump();
      expect(
        tester
            .widget<TextField>(find.byKey(const ValueKey('component-grams-0')))
            .controller
            ?.text,
        '210',
      );
      expect(
        tester
            .widget<Text>(find.byKey(const ValueKey('component-calories-0')))
            .data,
        '714 kcal',
      );
      expect(find.text('31.5 g'), findsOneWidget);

      await tester.tap(find.byKey(const ValueKey('component-minus-0')));
      await tester.pump();
      expect(
        tester
            .widget<TextField>(find.byKey(const ValueKey('component-grams-0')))
            .controller
            ?.text,
        '200',
      );

      await tester.enterText(
        find.byKey(const ValueKey('component-grams-0')),
        '150',
      );
      await tester.pump();
      expect(
        tester
            .widget<TextField>(find.byKey(const ValueKey('component-grams-0')))
            .controller
            ?.text,
        '150',
      );
      expect(
        tester
            .widget<Text>(find.byKey(const ValueKey('component-calories-0')))
            .data,
        '510 kcal',
      );
      expect(find.text('22.5 g'), findsOneWidget);
    },
  );

  testWidgets('a component edited down to zero can be brought back', (
    tester,
  ) async {
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Bánh mì thập cẩm',
      'source': 'vision',
      'nutrition': {
        'total_calories': 680,
        'total_grams': 200,
        'items': [
          {
            'item_name': 'Bánh mì thập cẩm',
            'grams': 200,
            'calories': 680,
            'protein_g': 30,
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

    final toggle = find.byKey(const ValueKey('component-edit-toggle-0'));
    await tester.ensureVisible(toggle);
    await tester.pumpAndSettle();
    await tester.tap(toggle);
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byKey(const ValueKey('component-grams-0')),
      '0',
    );
    await tester.pump();
    expect(
      tester
          .widget<Text>(find.byKey(const ValueKey('component-calories-0')))
          .data,
      '0 kcal',
    );

    // Về 0 rồi vẫn phải quy đổi lại được: mật độ dinh dưỡng lấy từ giá trị gốc.
    await tester.enterText(
      find.byKey(const ValueKey('component-grams-0')),
      '150',
    );
    await tester.pump();
    expect(
      tester
          .widget<Text>(find.byKey(const ValueKey('component-calories-0')))
          .data,
      '510 kcal',
    );
  });

  testWidgets('dishes without catalog data show a dash instead of 0 kcal', (
    tester,
  ) async {
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Phở bò',
      'source': 'vision',
      'dishes': [
        {'dish_name': 'Phở bò', 'grams': 500, 'found_in_db': false},
        {'dish_name': 'Quẩy', 'grams': 40, 'found_in_db': false},
      ],
    });

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalysisResultScreen(result: result),
      ),
    );

    // 2 dòng thành phần + 1 tổng ở phần tóm tắt.
    expect(find.text('500 g  •  — kcal'), findsOneWidget);
    expect(find.text('40 g  •  — kcal'), findsOneWidget);
    expect(find.text('— kcal'), findsOneWidget);
    expect(find.text('0 kcal'), findsNothing);
  });
}
