class AnalyzeResult {
  const AnalyzeResult({
    required this.source,
    required this.dishes,
    required this.missingItems,
    this.recognitionEventId,
    this.dishName,
    this.cvConfidence,
    this.recognitionConfidence,
    this.nutrition,
    this.reasoning,
    this.error,
    this.matches = const [],
    this.referenceOnly = false,
    this.warning,
  });

  factory AnalyzeResult.fromJson(Map<String, dynamic> json) {
    final dishesJson = json['dishes'];
    final missingJson = json['missing_items'];
    final matchesJson = json['matches'];
    final matches = matchesJson is List
        ? matchesJson
              .whereType<Map>()
              .map<AnalyzeMatch>(
                (match) =>
                    AnalyzeMatch.fromJson(Map<String, dynamic>.from(match)),
              )
              .toList(growable: false)
        : const <AnalyzeMatch>[];
    return AnalyzeResult(
      dishName: json['dish_name'] as String?,
      source: json['source'] as String? ?? 'vision',
      recognitionEventId: json['recognition_event_id'] as String?,
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
      matches: matches,
      referenceOnly: json['reference_only'] as bool? ?? false,
      warning: _toStringOrNull(json['warning']),
    );
  }

  final String? dishName;
  final String source;
  final String? recognitionEventId;
  final double? cvConfidence;
  final double? recognitionConfidence;
  final NutritionSummary? nutrition;
  final List<AnalyzedDish> dishes;
  final String? reasoning;
  final List<String> missingItems;
  final String? error;
  final List<AnalyzeMatch> matches;
  final bool referenceOnly;
  final String? warning;

  bool get isTextAnalysis => source.startsWith('text_');

  /// Nhân toàn bộ kết quả với [factor].
  ///
  /// Không tự cắt hệ số: dialog nhập "Tổng khối lượng (g)" đã giới hạn khoảng
  /// hợp lệ rồi. Cắt âm thầm ở đây khiến người dùng nhập 2000 g mà màn hình
  /// hiện 1480 g, không có cách nào biết.
  AnalyzeResult scaled(double factor) {
    final safeFactor = factor.isFinite && factor > 0 ? factor : 1.0;
    return AnalyzeResult(
      dishName: dishName,
      source: source,
      recognitionEventId: recognitionEventId,
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
              servingLabel: safeFactor == 1 ? dish.servingLabel : null,
            ),
          )
          .toList(growable: false),
      reasoning: reasoning,
      missingItems: missingItems,
      error: error,
      matches: matches,
      referenceOnly: referenceOnly,
      warning: warning,
    );
  }

  AnalyzeResult scaledItem(int index, double grams) {
    final currentNutrition = nutrition;
    if (currentNutrition == null ||
        index < 0 ||
        index >= currentNutrition.items.length) {
      return this;
    }
    final safeGrams = grams.clamp(0.0, 10000.0).toDouble();
    final itemName = currentNutrition.items[index].name;
    return AnalyzeResult(
      dishName: dishName,
      source: source,
      recognitionEventId: recognitionEventId,
      cvConfidence: cvConfidence,
      recognitionConfidence: recognitionConfidence,
      nutrition: currentNutrition.scaledItem(index, safeGrams),
      dishes: dishes
          .map(
            (dish) => dish.name == itemName
                ? AnalyzedDish(
                    // Gán thẳng khối lượng mới, không nhân hệ số: khi grams
                    // hiện tại là 0 thì không có hệ số nào chia được.
                    name: dish.name,
                    grams: safeGrams,
                    isSide: dish.isSide,
                    foundInDatabase: dish.foundInDatabase,
                    recognitionConfidence: dish.recognitionConfidence,
                    portionSource: dish.portionSource,
                    servingLabel: safeGrams == dish.grams
                        ? dish.servingLabel
                        : null,
                  )
                : dish,
          )
          .toList(growable: false),
      reasoning: reasoning,
      missingItems: missingItems,
      error: error,
      matches: matches,
      referenceOnly: referenceOnly,
      warning: warning,
    );
  }

  /// Đổi tên món theo đính chính của người dùng, giữ nguyên mọi số liệu.
  ///
  /// Chỉ sửa nhãn: người dùng biết mình ăn món gì, nhưng khối lượng và dinh
  /// dưỡng thì vẫn là ước lượng của hệ thống nên không được bịa lại.
  AnalyzeResult renamed(String newDishName) {
    final name = newDishName.trim();
    if (name.isEmpty) return this;
    return AnalyzeResult(
      dishName: name,
      source: source,
      recognitionEventId: recognitionEventId,
      cvConfidence: cvConfidence,
      recognitionConfidence: recognitionConfidence,
      nutrition: nutrition,
      dishes: dishes,
      reasoning: reasoning,
      missingItems: missingItems,
      error: error,
      matches: matches,
      referenceOnly: referenceOnly,
      warning: warning,
    );
  }
}

class AnalyzeMatch {
  const AnalyzeMatch({
    required this.recordId,
    required this.canonicalName,
    required this.catalogType,
    required this.source,
    required this.nutritionBasis,
    required this.reviewStatus,
  });

  factory AnalyzeMatch.fromJson(Map<String, dynamic> json) {
    return AnalyzeMatch(
      recordId: json['record_id'] as String? ?? '',
      canonicalName: json['canonical_name'] as String? ?? 'Món ăn',
      catalogType: json['catalog_type'] as String? ?? 'unknown',
      source: json['source'] as String? ?? 'unknown',
      nutritionBasis: json['nutrition_basis'] as String? ?? 'unknown',
      reviewStatus: json['review_status'] as String? ?? 'unknown',
    );
  }

  final String recordId;
  final String canonicalName;
  final String catalogType;
  final String source;
  final String nutritionBasis;
  final String reviewStatus;
}

class AnalyzedDish {
  const AnalyzedDish({
    required this.name,
    required this.grams,
    required this.isSide,
    required this.foundInDatabase,
    this.recognitionConfidence,
    this.portionSource = 'unknown',
    this.servingLabel,
  });

  factory AnalyzedDish.fromJson(Map<String, dynamic> json) {
    return AnalyzedDish(
      name: json['dish_name'] as String? ?? 'Món chưa xác định',
      grams: _toDouble(json['grams']),
      isSide: json['is_side'] as bool? ?? false,
      foundInDatabase: json['found_in_db'] as bool? ?? false,
      recognitionConfidence: _toDoubleOrNull(json['recognition_confidence']),
      portionSource: json['portion_source'] as String? ?? 'unknown',
      servingLabel: _toStringOrNull(json['serving_label']),
    );
  }

  final String name;
  final double grams;
  final bool isSide;
  final bool foundInDatabase;
  final double? recognitionConfidence;
  final String portionSource;
  final String? servingLabel;
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
          .map((item) => item.scaledTo(item.grams * factor))
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
          (entry) =>
              entry.key == index ? entry.value.scaledTo(grams) : entry.value,
        )
        .toList(growable: false);
    return NutritionSummary(
      items: updatedItems,
      totalCalories: updatedItems.fold(0.0, (sum, item) => sum + item.calories),
      totalProteinGrams: updatedItems.fold(
        0.0,
        (sum, item) => sum + item.proteinGrams,
      ),
      totalFatGrams: updatedItems.fold(0.0, (sum, item) => sum + item.fatGrams),
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
    this.baseline,
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

  /// Giá trị gốc do API trả về, giữ lại làm mốc quy đổi.
  ///
  /// Nếu chỉ dựa vào [grams] hiện tại, một thành phần bị sửa về 0 g sẽ mất luôn
  /// mật độ dinh dưỡng (0 chia 0) và mọi lần chỉnh sau đó đều ra 0 kcal.
  final NutritionItem? baseline;

  NutritionItem scaledTo(double targetGrams) {
    final basis = baseline ?? this;
    final factor = basis.grams > 0 ? targetGrams / basis.grams : 0.0;
    return NutritionItem(
      name: name,
      grams: targetGrams,
      calories: basis.calories * factor,
      proteinGrams: basis.proteinGrams * factor,
      fatGrams: basis.fatGrams * factor,
      carbsGrams: basis.carbsGrams * factor,
      fiberGrams: basis.fiberGrams * factor,
      foundInDatabase: foundInDatabase,
      nutritionBasis: nutritionBasis,
      baseline: basis,
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

String? _toStringOrNull(Object? value) => switch (value) {
  final String text when text.trim().isNotEmpty => text.trim(),
  _ => null,
};
