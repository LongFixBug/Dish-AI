import 'package:balance/features/analyze/domain/analyze_result.dart';

enum MealType {
  breakfast('Bữa sáng'),
  lunch('Bữa trưa'),
  dinner('Bữa tối'),
  snack('Bữa phụ');

  const MealType(this.label);
  final String label;
}

class JournalEntry {
  const JournalEntry({
    required this.id,
    required this.dishName,
    required this.loggedAt,
    required this.mealType,
    required this.calories,
    required this.proteinGrams,
    required this.fatGrams,
    required this.carbsGrams,
    required this.fiberGrams,
    required this.totalGrams,
  });

  factory JournalEntry.fromAnalysis({
    required AnalyzeResult result,
    required DateTime loggedAt,
    required MealType mealType,
  }) {
    final nutrition = result.nutrition;
    return JournalEntry(
      id: '${loggedAt.microsecondsSinceEpoch}-${result.dishName ?? 'meal'}',
      dishName: result.dishName ?? 'Món ăn đã nhận diện',
      loggedAt: loggedAt,
      mealType: mealType,
      calories: nutrition?.totalCalories ?? 0,
      proteinGrams: nutrition?.totalProteinGrams ?? 0,
      fatGrams: nutrition?.totalFatGrams ?? 0,
      carbsGrams: nutrition?.totalCarbsGrams ?? 0,
      fiberGrams: nutrition?.totalFiberGrams ?? 0,
      totalGrams: nutrition?.totalGrams ?? 0,
    );
  }

  factory JournalEntry.fromJson(Map<String, dynamic> json) {
    return JournalEntry(
      id: json['id'] as String? ?? '',
      dishName: json['dish_name'] as String? ?? 'Món ăn',
      loggedAt:
          DateTime.tryParse(json['logged_at'] as String? ?? '') ??
          DateTime.now(),
      mealType: MealType.values.firstWhere(
        (value) => value.name == json['meal_type'],
        orElse: () => MealType.snack,
      ),
      calories: _doubleValue(json['calories']),
      proteinGrams: _doubleValue(json['protein_g']),
      fatGrams: _doubleValue(json['fat_g']),
      carbsGrams: _doubleValue(json['carbs_g']),
      fiberGrams: _doubleValue(json['fiber_g']),
      totalGrams: _doubleValue(json['total_grams']),
    );
  }

  final String id;
  final String dishName;
  final DateTime loggedAt;
  final MealType mealType;
  final double calories;
  final double proteinGrams;
  final double fatGrams;
  final double carbsGrams;
  final double fiberGrams;
  final double totalGrams;

  Map<String, dynamic> toJson() => {
    'id': id,
    'dish_name': dishName,
    'logged_at': loggedAt.toIso8601String(),
    'meal_type': mealType.name,
    'calories': calories,
    'protein_g': proteinGrams,
    'fat_g': fatGrams,
    'carbs_g': carbsGrams,
    'fiber_g': fiberGrams,
    'total_grams': totalGrams,
  };
}

double _doubleValue(Object? value) => switch (value) {
  final num number => number.toDouble(),
  _ => 0,
};
