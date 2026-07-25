class AnalyzeResult {
  const AnalyzeResult({
    required this.source,
    required this.dishes,
    required this.missingItems,
    this.dishName,
    this.cvConfidence,
    this.recognitionConfidence,
    this.nutrition,
    this.reasoning,
    this.error,
  });

  factory AnalyzeResult.fromJson(Map<String, dynamic> json) {
    final dishesJson = json['dishes'];
    final missingJson = json['missing_items'];
    return AnalyzeResult(
      dishName: json['dish_name'] as String?,
      source: json['source'] as String? ?? 'vision',
      cvConfidence: _toDoubleOrNull(json['cv_confidence']),
      recognitionConfidence: _toDoubleOrNull(json['recognition_confidence']),
      nutrition: switch (json['nutrition']) {
        final Map<String, dynamic> value => NutritionSummary.fromJson(value),
        _ => null,
      },
      dishes: dishesJson is List
          ? dishesJson
                .whereType<Map<String, dynamic>>()
                .map(AnalyzedDish.fromJson)
                .toList(growable: false)
          : const [],
      reasoning: json['vision_reasoning'] as String?,
      missingItems: missingJson is List
          ? missingJson.whereType<String>().toList(growable: false)
          : const [],
      error: json['error'] as String?,
    );
  }

  final String? dishName;
  final String source;
  final double? cvConfidence;
  final double? recognitionConfidence;
  final NutritionSummary? nutrition;
  final List<AnalyzedDish> dishes;
  final String? reasoning;
  final List<String> missingItems;
  final String? error;

  AnalyzeResult scaled(double factor) {
    final safeFactor = factor.clamp(0.25, 4.0);
    return AnalyzeResult(
      dishName: dishName,
      source: source,
      cvConfidence: cvConfidence,
      recognitionConfidence: recognitionConfidence,
      nutrition: nutrition?.scaled(safeFactor),
      dishes: dishes
          .map(
            (dish) => AnalyzedDish(
              name: dish.name,
              grams: dish.grams * safeFactor,
              isSide: dish.isSide,
              foundInDatabase: dish.foundInDatabase,
              recognitionConfidence: dish.recognitionConfidence,
              portionSource: dish.portionSource,
            ),
          )
          .toList(growable: false),
      reasoning: reasoning,
      missingItems: missingItems,
      error: error,
    );
  }
}

class AnalyzedDish {
  const AnalyzedDish({
    required this.name,
    required this.grams,
    required this.isSide,
    required this.foundInDatabase,
    this.recognitionConfidence,
    this.portionSource = 'unknown',
  });

  factory AnalyzedDish.fromJson(Map<String, dynamic> json) {
    return AnalyzedDish(
      name: json['dish_name'] as String? ?? 'Món chưa xác định',
      grams: _toDouble(json['grams']),
      isSide: json['is_side'] as bool? ?? false,
      foundInDatabase: json['found_in_db'] as bool? ?? false,
      recognitionConfidence: _toDoubleOrNull(json['recognition_confidence']),
      portionSource: json['portion_source'] as String? ?? 'unknown',
    );
  }

  final String name;
  final double grams;
  final bool isSide;
  final bool foundInDatabase;
  final double? recognitionConfidence;
  final String portionSource;
}

class NutritionSummary {
  const NutritionSummary({
    required this.items,
    required this.totalCalories,
    required this.totalProteinGrams,
    required this.totalFatGrams,
    required this.totalCarbsGrams,
    required this.totalFiberGrams,
    required this.totalGrams,
    required this.confidenceScore,
    required this.catalogCoverageScore,
    required this.per100gAvailable,
  });

  factory NutritionSummary.fromJson(Map<String, dynamic> json) {
    final itemsJson = json['items'];
    return NutritionSummary(
      items: itemsJson is List
          ? itemsJson
                .whereType<Map>()
                .map(
                  (item) =>
                      NutritionItem.fromJson(Map<String, dynamic>.from(item)),
                )
                .toList(growable: false)
          : const [],
      totalCalories: _toDouble(json['total_calories']),
      totalProteinGrams: _toDouble(json['total_protein_g']),
      totalFatGrams: _toDouble(json['total_fat_g']),
      totalCarbsGrams: _toDouble(json['total_carbs_g']),
      totalFiberGrams: _toDouble(json['total_fiber_g']),
      totalGrams: _toDouble(json['total_grams']),
      confidenceScore: _toDouble(json['confidence_score']),
      catalogCoverageScore: _toDouble(
        json['catalog_coverage_score'] ?? json['confidence_score'],
      ),
      per100gAvailable: json['per_100g_available'] as bool? ?? false,
    );
  }

  final List<NutritionItem> items;
  final double totalCalories;
  final double totalProteinGrams;
  final double totalFatGrams;
  final double totalCarbsGrams;
  final double totalFiberGrams;
  final double totalGrams;
  final double confidenceScore;
  final double catalogCoverageScore;
  final bool per100gAvailable;

  NutritionSummary scaled(double factor) {
    return NutritionSummary(
      items: items
          .map(
            (item) => NutritionItem(
              name: item.name,
              grams: item.grams * factor,
              calories: item.calories * factor,
              foundInDatabase: item.foundInDatabase,
              nutritionBasis: item.nutritionBasis,
            ),
          )
          .toList(growable: false),
      totalCalories: totalCalories * factor,
      totalProteinGrams: totalProteinGrams * factor,
      totalFatGrams: totalFatGrams * factor,
      totalCarbsGrams: totalCarbsGrams * factor,
      totalFiberGrams: totalFiberGrams * factor,
      totalGrams: totalGrams * factor,
      confidenceScore: confidenceScore,
      catalogCoverageScore: catalogCoverageScore,
      per100gAvailable: per100gAvailable,
    );
  }
}

class NutritionItem {
  const NutritionItem({
    required this.name,
    required this.grams,
    required this.calories,
    required this.foundInDatabase,
    this.nutritionBasis = 'unknown',
  });

  factory NutritionItem.fromJson(Map<String, dynamic> json) {
    return NutritionItem(
      name: json['item_name'] as String? ?? 'Thành phần',
      grams: _toDouble(json['grams']),
      calories: _toDouble(json['calories']),
      foundInDatabase: json['found_in_db'] as bool? ?? false,
      nutritionBasis: json['nutrition_basis'] as String? ?? 'unknown',
    );
  }

  final String name;
  final double grams;
  final double calories;
  final bool foundInDatabase;
  final String nutritionBasis;
}

double _toDouble(Object? value) => switch (value) {
  final num number => number.toDouble(),
  _ => 0,
};

double? _toDoubleOrNull(Object? value) => switch (value) {
  final num number => number.toDouble(),
  _ => null,
};
