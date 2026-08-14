import 'dart:async';
import 'dart:typed_data';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/data/analyze_api.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

void main() {
  testWidgets('user can analyze a food name without an image', (tester) async {
    String? receivedName;
    double? receivedGrams;
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Sữa bò tươi',
      'source': 'text_catalog',
      'nutrition': {
        'dish_name': 'Sữa bò tươi',
        'total_calories': 120,
        'total_protein_g': 6.4,
        'total_fat_g': 7,
        'total_carbs_g': 9.6,
        'total_fiber_g': 0,
        'total_grams': 200,
        'confidence_score': 1,
      },
      'dishes': <Object>[],
    });

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(
          analyzeText: ({required foodName, required grams}) async {
            receivedName = foodName;
            receivedGrams = grams;
            return result;
          },
        ),
      ),
    );

    await tester.tap(find.text('Nhập món'));
    await tester.pump();
    expect(find.byKey(const ValueKey('text-food-name')), findsOneWidget);
    expect(find.byKey(const ValueKey('text-food-grams')), findsOneWidget);
    expect(find.text('100'), findsOneWidget);

    await tester.enterText(
      find.byKey(const ValueKey('text-food-name')),
      'Sữa bò tươi',
    );
    await tester.tap(find.text('Phân tích món'));
    await tester.pumpAndSettle();

    expect(receivedName, 'Sữa bò tươi');
    expect(receivedGrams, 100.0);
    expect(find.byType(AnalysisResultScreen), findsOneWidget);
  });

  testWidgets('ambiguous food names show catalog candidates to choose', (
    tester,
  ) async {
    var calls = 0;
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Gạo tẻ',
      'source': 'text_catalog',
      'nutrition': {
        'dish_name': 'Gạo tẻ',
        'total_calories': 350,
        'total_grams': 100,
      },
      'dishes': <Object>[],
    });

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(
          analyzeText: ({required foodName, required grams}) async {
            if (calls++ == 0) {
              return AnalyzeResult.fromJson({
                'dish_name': foodName,
                'source': 'text_ambiguous',
                'warning': 'Có nhiều món phù hợp.',
                'matches': [
                  {
                    'record_id': 'dish-1',
                    'canonical_name': 'Gạo tẻ',
                    'catalog_type': 'vn_dish',
                    'source': 'vnmeal',
                    'nutrition_basis': 'per_gram',
                    'review_status': 'reviewed',
                  },
                  {
                    'record_id': 'nri-1',
                    'canonical_name': 'Gạo tẻ lứt',
                    'catalog_type': 'nrihcm_food',
                    'source': 'nrihcm_raw',
                    'nutrition_basis': 'per_100g',
                    'review_status': 'raw',
                  },
                ],
              });
            }
            return result;
          },
        ),
      ),
    );

    await tester.tap(find.text('Nhập món'));
    await tester.pump();
    await tester.enterText(find.byKey(const ValueKey('text-food-name')), 'gạo');
    await tester.tap(find.byKey(const ValueKey('text-analyze-submit')));
    await tester.pumpAndSettle();

    expect(find.text('Có nhiều món phù hợp.'), findsOneWidget);
    expect(find.text('Gạo tẻ'), findsOneWidget);
    expect(
      find.textContaining('Dữ liệu Viện Dinh dưỡng đã craw'),
      findsOneWidget,
    );

    await tester.tap(find.text('Gạo tẻ'));
    await tester.pump();
    final field = tester.widget<TextField>(
      find.byKey(const ValueKey('text-food-name')),
    );
    expect(field.controller!.text, 'Gạo tẻ');

    await tester.tap(find.byKey(const ValueKey('text-analyze-submit')));
    await tester.pumpAndSettle();
    expect(calls, 2);
    expect(find.byType(AnalysisResultScreen), findsOneWidget);
  });

  testWidgets('selected photos require confirmation before AI analysis', (
    tester,
  ) async {
    final analysis = Completer<AnalyzeResult>();
    var analysisCalls = 0;
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
          analyzeImage: ({required bytes, required filename}) {
            analysisCalls++;
            return analysis.future;
          },
        ),
      ),
    );

    expect(find.text('Chụp món ăn'), findsOneWidget);
    expect(find.byKey(const ValueKey('camera-preview')), findsOneWidget);
    expect(find.text('Bắt đầu quét món ăn'), findsOneWidget);
    expect(
      find.text('Đưa món vào khung, chụp từ trên xuống, đủ sáng.'),
      findsOneWidget,
    );
    expect(find.text('Thư viện'), findsOneWidget);
    expect(find.text('Mẹo chụp'), findsOneWidget);

    await tester.tap(find.text('Thư viện'));
    await tester.pump();
    expect(analysisCalls, 0);
    expect(find.text('Ảnh đã sẵn sàng'), findsOneWidget);
    expect(find.text('Chụp lại'), findsOneWidget);
    expect(find.text('Dùng ảnh này'), findsOneWidget);

    await tester.tap(find.text('Dùng ảnh này'));
    await tester.pump();
    expect(analysisCalls, 1);
    expect(find.text('Balance đang đọc ảnh'), findsOneWidget);
    expect(
      find.text('Đợi một lát để AI đối chiếu món và khẩu phần.'),
      findsOneWidget,
    );

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

    await tester.tap(find.text('Dùng ảnh này'));
    await tester.pumpAndSettle();

    expect(find.text('Chưa phân tích được ảnh'), findsOneWidget);
    expect(
      find.text(
        'Chưa kết nối được để phân tích ảnh. Kiểm tra mạng rồi thử lại.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('Không kết nối được backend'), findsNothing);
    expect(find.text('Thử lại'), findsOneWidget);
  });

  testWidgets(
    'shows the backend analysis error instead of calling it a network failure',
    (tester) async {
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
              throw const AnalyzeApiException(
                'Dịch vụ nhận diện đang tạm gián đoạn. Vui lòng thử lại sau.',
              );
            },
          ),
        ),
      );

      await tester.tap(find.byKey(const ValueKey('camera-shutter')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dùng ảnh này'));
      await tester.pumpAndSettle();

      expect(
        find.text(
          'Dịch vụ nhận diện đang tạm gián đoạn. Vui lòng thử lại sau.',
        ),
        findsOneWidget,
      );
      expect(
        find.text(
          'Chưa kết nối được để phân tích ảnh. Kiểm tra mạng rồi thử lại.',
        ),
        findsNothing,
      );
    },
  );

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

  testWidgets('capture entry uses a clear camera-first action sheet', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(pickImage: (_) async => null),
      ),
    );

    expect(find.byKey(const ValueKey('capture-action-sheet')), findsOneWidget);
    expect(find.text('Bắt đầu quét món ăn'), findsOneWidget);
    expect(find.text('Mở camera'), findsOneWidget);
    expect(find.text('Thư viện'), findsOneWidget);
    expect(find.text('Mẹo chụp'), findsOneWidget);
  });

  testWidgets('capture controls use the inked paper-card treatment', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: AnalyzeScreen(pickImage: (_) async => null),
      ),
    );

    final card = tester.widget<SketchCard>(
      find.byKey(const ValueKey('capture-action-sheet')),
    );
    expect(card.color, isNull);
    expect(
      BalanceTheme.paletteOf(
        tester.element(find.byKey(const ValueKey('capture-action-sheet'))),
      ).surface,
      BalanceColors.paper,
    );
    expect(card.shadow, isTrue);
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
    expect(find.text('Mở camera'), findsOneWidget);
    expect(find.text('Thư viện'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
