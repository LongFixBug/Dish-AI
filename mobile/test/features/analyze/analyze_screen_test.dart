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
    expect(find.byKey(const ValueKey('camera-preview')), findsOneWidget);
    expect(find.text('Đặt món ở giữa vùng quét'), findsOneWidget);
    expect(find.text('Chụp rõ món ăn • nơi đủ sáng'), findsOneWidget);
    expect(find.text('Thư viện'), findsOneWidget);
    expect(find.text('Mẹo chụp'), findsOneWidget);

    await tester.tap(find.text('Thư viện'));
    await tester.pump();
    expect(find.text('Đang quét món ăn'), findsOneWidget);
    expect(find.text('Vạch quét cong khi chạm tới món ăn'), findsOneWidget);

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

  testWidgets('camera tips are available without leaving the capture screen', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(pickImage: (_) async => null),
      ),
    );

    await tester.tap(find.text('Mẹo chụp'));
    await tester.pump();

    expect(
      find.text('Chụp từ trên xuống, đủ sáng và lấy trọn phần ăn.'),
      findsOneWidget,
    );
    expect(find.byType(AnalyzeScreen), findsOneWidget);
  });

  testWidgets('gallery photo stays smaller inside the restored capture frame', (
    tester,
  ) async {
    final analysis = Completer<AnalyzeResult>();
    final image = XFile.fromData(
      Uint8List.fromList([0xff, 0xd8, 0xff]),
      name: 'pho-bo.jpg',
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

    await tester.tap(find.text('Thư viện'));
    await tester.pump();

    final canvas = tester.getSize(find.byKey(const ValueKey('camera-preview')));
    final photo = tester.getSize(
      find.byKey(const ValueKey('gallery-photo-preview')),
    );
    expect(photo.width, lessThan(canvas.width));
    expect(photo.height, lessThan(canvas.height));
    expect(find.byKey(const ValueKey('camera-preview-frame')), findsOneWidget);
    expect(find.byKey(const ValueKey('capture-focus-corners')), findsOneWidget);
    final photoImages = tester.widgetList<Image>(
      find.descendant(
        of: find.byKey(const ValueKey('gallery-photo-preview')),
        matching: find.byType(Image),
      ),
    );
    expect(photoImages, isNotEmpty);
    expect(photoImages.every((image) => image.fit == BoxFit.contain), isTrue);
    expect(find.text('Đặt món ở giữa vùng quét'), findsNothing);
  });

  testWidgets('camera layout fits a compact phone without overflowing', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(pickImage: (_) async => null),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('camera-preview')), findsOneWidget);
    expect(find.text('Chụp ảnh'), findsOneWidget);
    expect(find.text('Thư viện'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
