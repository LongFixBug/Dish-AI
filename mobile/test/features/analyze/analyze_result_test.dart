import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('parses the nutrition contract returned by FastAPI', () {
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Phở bò + Quẩy',
      'source': 'vision',
      'cv_confidence': 0.72,
      'recognition_confidence': 0.84,
      'nutrition': {
        'dish_name': 'Phở bò + Quẩy',
        'total_calories': 615.4,
        'total_protein_g': 31.2,
        'total_fat_g': 19.5,
        'total_carbs_g': 78.3,
        'total_fiber_g': 4.2,
        'total_grams': 430,
        'confidence_score': 0.5,
        'catalog_coverage_score': 0.5,
        'per_100g_available': true,
        'items': [
          {
            'item_name': 'Phở bò',
            'grams': 380,
            'calories': 540,
            'protein_g': 30,
            'fat_g': 18,
            'carbs_g': 70,
            'fiber_g': 3,
            'found_in_db': true,
            'nutrition_basis': 'per_gram_scaled',
          },
        ],
      },
      'dishes': [
        {
          'dish_name': 'Phở bò',
          'grams': 380,
          'is_side': false,
          'found_in_db': true,
          'recognition_confidence': 0.86,
          'portion_source': 'vision',
        },
        {
          'dish_name': 'Quẩy',
          'grams': 50,
          'is_side': true,
          'found_in_db': false,
        },
      ],
      'missing_items': ['Quẩy'],
    });

    expect(result.dishName, 'Phở bò + Quẩy');
    expect(result.nutrition?.totalCalories, 615.4);
    expect(result.recognitionConfidence, 0.84);
    expect(result.nutrition?.catalogCoverageScore, 0.5);
    expect(result.nutrition?.per100gAvailable, isTrue);
    expect(result.nutrition?.totalGrams, 430);
    expect(result.nutrition?.items.single.name, 'Phở bò');
    expect(result.nutrition?.items.single.calories, 540);
    expect(result.nutrition?.items.single.nutritionBasis, 'per_gram_scaled');
    expect(result.dishes, hasLength(2));
    expect(result.dishes.last.isSide, isTrue);
    expect(result.dishes.last.foundInDatabase, isFalse);
    expect(result.dishes.first.recognitionConfidence, 0.86);
    expect(result.dishes.first.portionSource, 'vision');
    expect(result.missingItems, ['Quẩy']);
  });

  test(
    'keeps a successful response usable when optional fields are absent',
    () {
      final result = AnalyzeResult.fromJson({
        'source': 'vision',
        'dishes': <Object>[],
      });

      expect(result.dishName, isNull);
      expect(result.nutrition, isNull);
      expect(result.error, isNull);
      expect(result.missingItems, isEmpty);
    },
  );
}
