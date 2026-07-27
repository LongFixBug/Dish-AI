/// Một món được máy chủ gợi ý, kèm lý do đọc được cho người dùng.
class SuggestedDish {
  const SuggestedDish({
    required this.dishName,
    required this.grams,
    required this.calories,
    required this.proteinGrams,
    required this.fatGrams,
    required this.carbsGrams,
    required this.reason,
  });

  factory SuggestedDish.fromJson(Map<String, dynamic> json) => SuggestedDish(
    dishName: json['dish_name'] as String? ?? 'Món ăn',
    grams: _toDouble(json['grams']),
    calories: _toDouble(json['calories']),
    proteinGrams: _toDouble(json['protein_g']),
    fatGrams: _toDouble(json['fat_g']),
    carbsGrams: _toDouble(json['carbs_g']),
    reason: json['reason'] as String? ?? '',
  );

  final String dishName;
  final double grams;
  final double calories;
  final double proteinGrams;
  final double fatGrams;
  final double carbsGrams;
  final String reason;
}

/// Khoảng dinh dưỡng còn lại của ngày.
class RemainingNutrition {
  const RemainingNutrition({
    required this.calories,
    required this.proteinGrams,
    required this.fatGrams,
    required this.carbsGrams,
  });

  factory RemainingNutrition.fromJson(Map<String, dynamic> json) =>
      RemainingNutrition(
        calories: _toDouble(json['calories']),
        proteinGrams: _toDouble(json['protein_g']),
        fatGrams: _toDouble(json['fat_g']),
        carbsGrams: _toDouble(json['carbs_g']),
      );

  final double calories;
  final double proteinGrams;
  final double fatGrams;
  final double carbsGrams;
}

/// Kết quả một lượt gợi ý.
class SuggestionResult {
  const SuggestionResult({
    required this.remaining,
    required this.dishes,
    required this.allergyFilterIsPartial,
  });

  factory SuggestionResult.fromJson(Map<String, dynamic> json) {
    final dishes = json['suggestions'];
    final remaining = json['remaining'];
    return SuggestionResult(
      remaining: remaining is Map<String, dynamic>
          ? RemainingNutrition.fromJson(remaining)
          : const RemainingNutrition(
              calories: 0,
              proteinGrams: 0,
              fatGrams: 0,
              carbsGrams: 0,
            ),
      dishes: dishes is List
          ? dishes
                .whereType<Map>()
                .map(
                  (item) =>
                      SuggestedDish.fromJson(Map<String, dynamic>.from(item)),
                )
                .toList(growable: false)
          : const [],
      // Bộ lọc dị ứng chỉ soi được TÊN món, không biết thành phần bên trong.
      // Máy chủ bật cờ này để màn hình nói rõ, tránh để người dùng tin nhầm
      // là đã lọc an toàn tuyệt đối.
      allergyFilterIsPartial:
          json['allergy_filter_is_partial'] as bool? ?? false,
    );
  }

  final RemainingNutrition remaining;
  final List<SuggestedDish> dishes;
  final bool allergyFilterIsPartial;
}

double _toDouble(Object? value) => switch (value) {
  final num number => number.toDouble(),
  _ => 0,
};
