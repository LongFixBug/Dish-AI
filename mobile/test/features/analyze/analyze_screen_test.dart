import 'dart:async';
import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

void main() {
  testWidgets('selecting a photo shows loading and then nutrition', (
    tester,
  ) async {
    final analysis = Completer<AnalyzeResult>();
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Bún bò Huế',
      'source': 'vision',
      'nutrition': {
        'dish_name': 'Bún bò Huế',
        'total_calories': 534,
        'total_protein_g': 28,
        'total_fat_g': 17,
        'total_carbs_g': 67,
        'total_fiber_g': 3.5,
        'total_grams': 520,
        'confidence_score': 1,
      },
      'dishes': <Object>[],
    });
    final image = XFile.fromData(
      Uint8List.fromList([0xff, 0xd8, 0xff]),
      name: 'bun-bo.jpg',
      mimeType: 'image/jpeg',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(
          pickImage: (_) async => image,
          analyzeImage: ({required bytes, required filename}) =>
              analysis.future,
        ),
      ),
    );

    expect(find.text('Chụp món ăn'), findsOneWidget);
    expect(find.text('Chọn ảnh từ thư viện'), findsOneWidget);

    await tester.tap(find.text('Chọn ảnh từ thư viện'));
    await tester.pump();
    expect(find.text('Balance đang xem món ăn...'), findsOneWidget);

    analysis.complete(result);
    await tester.pumpAndSettle();
    expect(find.byType(AnalysisResultScreen), findsOneWidget);
    expect(find.text('Kết quả phân tích'), findsOneWidget);
    expect(find.text('Bún bò Huế'), findsOneWidget);
    expect(find.text('534 kcal'), findsOneWidget);
    expect(find.text('28 g'), findsOneWidget);
    expect(find.text('Thêm vào nhật ký'), findsOneWidget);
  });

  testWidgets('a failed request gives retry actions instead of crashing', (
    tester,
  ) async {
    final image = XFile.fromData(
      Uint8List.fromList([0xff, 0xd8]),
      name: 'food.jpg',
    );

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(
          pickImage: (_) async => image,
          analyzeImage: ({required bytes, required filename}) async {
            throw Exception('Không kết nối được backend');
          },
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('camera-shutter')));
    await tester.pumpAndSettle();

    expect(find.text('Chưa phân tích được ảnh'), findsOneWidget);
    expect(find.textContaining('Không kết nối được backend'), findsOneWidget);
    expect(find.text('Thử lại'), findsOneWidget);
  });
}
