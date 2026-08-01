@Tags(['golden'])
library;

import 'dart:async';

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/food_photo.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/analyze/presentation/analysis_result_screen.dart';
import 'package:balance/features/analyze/presentation/scan_beam.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import '../../helpers/load_test_fonts.dart';

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await loadBalanceTestFonts();
  });

  testWidgets('camera screen matches the approved visual', (tester) async {
    await _setPhoneSize(tester);
    await tester.pumpWidget(_testApp(const AnalyzeScreen()));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(AnalyzeScreen),
      matchesGoldenFile('goldens/camera_screen.png'),
    );
  });

  testWidgets('3D scan reveal matches the approved depth frame', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(320, 480));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final data = await rootBundle.load(FoodPhoto.comTamAssetPath);
    final bytes = data.buffer.asUint8List(
      data.offsetInBytes,
      data.lengthInBytes,
    );

    await tester.pumpWidget(
      _testApp(
        Scaffold(body: ScanDepthFrame(imageBytes: bytes, progress: 0.58)),
      ),
    );
    final context = tester.element(find.byType(ScanDepthFrame));
    await tester.runAsync(() => precacheImage(MemoryImage(bytes), context));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(ScanDepthFrame),
      matchesGoldenFile('goldens/scan_depth_frame.png'),
    );
  });

  testWidgets('camera loading state shows the raised 3D scan', (tester) async {
    await _setPhoneSize(tester);
    final data = await rootBundle.load(FoodPhoto.comTamAssetPath);
    final bytes = data.buffer.asUint8List(
      data.offsetInBytes,
      data.lengthInBytes,
    );
    final analysis = Completer<AnalyzeResult>();

    await tester.pumpWidget(
      _testApp(
        AnalyzeScreen(
          pickImage: (_) async =>
              XFile.fromData(bytes, name: 'com-tam.png', mimeType: 'image/png'),
          analyzeImage: ({required bytes, required filename}) =>
              analysis.future,
        ),
      ),
    );
    final context = tester.element(find.byType(AnalyzeScreen));
    await tester.runAsync(() => precacheImage(MemoryImage(bytes), context));
    await tester.tap(find.text('Thư viện'));
    await tester.pump();
    await tester.tap(find.text('Dùng ảnh này'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 1300));

    await expectLater(
      find.byType(AnalyzeScreen),
      matchesGoldenFile('goldens/camera_scanning_3d.png'),
    );
  });

  testWidgets('analysis result screen matches the approved visual', (
    tester,
  ) async {
    await _setPhoneSize(tester);
    await tester.pumpWidget(
      _testApp(AnalysisResultScreen(result: _sampleResult)),
    );
    final context = tester.element(find.byType(AnalysisResultScreen));
    await tester.runAsync(
      () => precacheImage(const AssetImage(FoodPhoto.comTamAssetPath), context),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(AnalysisResultScreen),
      matchesGoldenFile('goldens/analysis_result_screen.png'),
    );
  });

  testWidgets('suggestions screen matches the approved visual', (tester) async {
    await _setPhoneSize(tester);
    await tester.pumpWidget(_testApp(const SuggestionsScreen()));
    final context = tester.element(find.byType(SuggestionsScreen));
    await tester.runAsync(() async {
      await precacheImage(const AssetImage(FoodPhoto.caKhoAssetPath), context);
      await precacheImage(const AssetImage(FoodPhoto.bunGaAssetPath), context);
    });
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(SuggestionsScreen),
      matchesGoldenFile('goldens/suggestions_screen.png'),
    );
  });
}

Future<void> _setPhoneSize(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(390, 844));
  addTearDown(() => tester.binding.setSurfaceSize(null));
}

Widget _testApp(Widget home) {
  return MaterialApp(theme: BalanceTheme.light, home: home);
}

final _sampleResult = AnalyzeResult.fromJson({
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
        'found_in_db': true,
      },
      {
        'item_name': 'Sườn nướng',
        'grams': 120,
        'calories': 320,
        'found_in_db': true,
      },
      {'item_name': 'Trứng', 'grams': 50, 'calories': 70, 'found_in_db': true},
    ],
  },
  'dishes': <Object>[],
});
