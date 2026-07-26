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

  AnalyzeResult scaledItem(int index, double grams) {
    final currentNutrition = nutrition;
    if (currentNutrition == null ||
        index < 0 ||
        index >= currentNutrition.items.length) {
      return this;
    }
    final currentGrams = currentNutrition.items[index].grams;
    if (currentGrams <= 0) return this;
    final safeGrams = grams.clamp(0.0, 10000.0).toDouble();
    final factor = safeGrams / currentGrams;
    final itemName = currentNutrition.items[index].name;
    return AnalyzeResult(
      dishName: dishName,
      source: source,
      cvConfidence: cvConfidence,
      recognitionConfidence: recognitionConfidence,
      nutrition: currentNutrition.scaledItem(index, safeGrams),
      dishes: dishes
          .map(
            (dish) => dish.name == itemName
                ? AnalyzedDish(
                    name: dish.name,
                    grams: dish.grams * factor,
                    isSide: dish.isSide,
                    foundInDatabase: dish.foundInDatabase,
                    recognitionConfidence: dish.recognitionConfidence,
                    portionSource: dish.portionSource,
                  )
                : dish,
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
              proteinGrams: item.proteinGrams * factor,
              fatGrams: item.fatGrams * factor,
              carbsGrams: item.carbsGrams * factor,
              fiberGrams: item.fiberGrams * factor,
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

  NutritionSummary scaledItem(int index, double grams) {
    final updatedItems = items
        .asMap()
        .entries
        .map(
          (entry) => entry.key == index
              ? entry.value.scaledTo(grams)
              : entry.value,
        )
        .toList(growable: false);
    return NutritionSummary(
      items: updatedItems,
      totalCalories: updatedItems.fold(
        0.0,
        (sum, item) => sum + item.calories,
      ),
      totalProteinGrams: updatedItems.fold(
        0.0,
        (sum, item) => sum + item.proteinGrams,
      ),
      totalFatGrams: updatedItems.fold(
        0.0,
        (sum, item) => sum + item.fatGrams,
      ),
      totalCarbsGrams: updatedItems.fold(
        0.0,
        (sum, item) => sum + item.carbsGrams,
      ),
      totalFiberGrams: updatedItems.fold(
        0.0,
        (sum, item) => sum + item.fiberGrams,
      ),
      totalGrams: updatedItems.fold(0.0, (sum, item) => sum + item.grams),
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
    this.proteinGrams = 0,
    this.fatGrams = 0,
    this.carbsGrams = 0,
    this.fiberGrams = 0,
    this.nutritionBasis = 'unknown',
  });

  factory NutritionItem.fromJson(Map<String, dynamic> json) {
    return NutritionItem(
      name: json['item_name'] as String? ?? 'Thành phần',
      grams: _toDouble(json['grams']),
      calories: _toDouble(json['calories']),
      proteinGrams: _toDouble(json['protein_g']),
      fatGrams: _toDouble(json['fat_g']),
      carbsGrams: _toDouble(json['carbs_g']),
      fiberGrams: _toDouble(json['fiber_g']),
      foundInDatabase: json['found_in_db'] as bool? ?? false,
      nutritionBasis: json['nutrition_basis'] as String? ?? 'unknown',
    );
  }

  final String name;
  final double grams;
  final double calories;
  final double proteinGrams;
  final double fatGrams;
  final double carbsGrams;
  final double fiberGrams;
  final bool foundInDatabase;
  final String nutritionBasis;

  NutritionItem scaledTo(double targetGrams) {
    final factor = grams > 0 ? targetGrams / grams : 0.0;
    return NutritionItem(
      name: name,
      grams: targetGrams,
      calories: calories * factor,
      proteinGrams: proteinGrams * factor,
      fatGrams: fatGrams * factor,
      carbsGrams: carbsGrams * factor,
      fiberGrams: fiberGrams * factor,
      foundInDatabase: foundInDatabase,
      nutritionBasis: nutritionBasis,
    );
  }
}

double _toDouble(Object? value) => switch (value) {
  final num number => number.toDouble(),
  _ => 0,
};

double? _toDoubleOrNull(Object? value) => switch (value) {
  final num number => number.toDouble(),
  _ => null,
};
