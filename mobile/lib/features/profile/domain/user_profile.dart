import 'package:flutter/foundation.dart';

class UserProfile {
  const UserProfile({
    required this.name,
    required this.email,
    required this.age,
    required this.heightCm,
    required this.weightKg,
    required this.targetWeightKg,
    this.targetDays = 90,
    required this.gender,
    required this.activity,
    required this.goal,
    this.allergies = const [],
    this.medicalConditions = const [],
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      name: json['name'] as String? ?? 'Bạn',
      email: json['email'] as String? ?? '',
      age: _intValue(json['age'], 24),
      heightCm: _intValue(json['height_cm'], 170),
      weightKg: _intValue(json['weight_kg'], 65),
      targetWeightKg: _intValue(json['target_weight_kg'], 60),
      targetDays: _intValue(json['target_days'], 90),
      gender: json['gender'] as String? ?? 'Khác',
      activity: json['activity'] as String? ?? 'Vừa phải',
      goal: json['goal'] as String? ?? 'Giữ cân',
      allergies: _stringList(json['allergies']),
      medicalConditions: _stringList(json['medical_conditions']),
    );
  }

  final String name;
  final String email;
  final int age;
  final int heightCm;
  final int weightKg;
  final int targetWeightKg;
  final int targetDays;
  final String gender;
  final String activity;
  final String goal;
  final List<String> allergies;
  final List<String> medicalConditions;

  bool get hasNutritionSafetyFlags =>
      allergies.isNotEmpty || medicalConditions.isNotEmpty;

  NutritionTarget get nutritionTarget {
    final genderOffset = switch (gender) {
      'Nam' => 5.0,
      'Nữ' => -161.0,
      _ => -78.0,
    };
    final activityFactor = switch (activity) {
      'Ít vận động' => 1.2,
      'Nhẹ nhàng' => 1.375,
      'Năng động' => 1.725,
      _ => 1.55,
    };
    final basal =
        (10 * weightKg) + (6.25 * heightCm) - (5 * age) + genderOffset;
    final maintenance = (basal * activityFactor).round();
    final signedDelta = switch (goal) {
      'Giảm cân' when targetWeightKg < weightKg =>
        (targetWeightKg - weightKg) * 7700 / targetDays.clamp(1, 730),
      'Tăng cân' when targetWeightKg > weightKg =>
        (targetWeightKg - weightKg) * 7700 / targetDays.clamp(1, 730),
      _ => 0.0,
    };
    final goalDelta = signedDelta.clamp(-500.0, 500.0).round();
    final calories = (maintenance + goalDelta).clamp(1200, 4000);
    final proteinMin = (0.8 * weightKg).clamp(
      calories * 0.10 / 4,
      double.infinity,
    );
    final proteinTarget = proteinMin.clamp(
      calories * 0.15 / 4,
      double.infinity,
    );
    final proteinMax = proteinMin > calories * 0.25 / 4
        ? proteinMin
        : calories * 0.25 / 4;
    final fatMin = calories * 0.15 / 9;
    final fatTarget = calories * 0.25 / 9;
    final fatMax = calories * 0.30 / 9;
    final carbMin = calories * 0.45 / 4;
    final carbTarget =
        (calories - proteinTarget * 4 - fatTarget * 9).clamp(
          carbMin,
          double.infinity,
        ) /
        4;
    final carbMax = calories * 0.75 / 4;
    return NutritionTarget(
      maintenanceCalories: maintenance,
      calories: calories,
      proteinTargetG: proteinTarget,
      carbohydrateTargetG: carbTarget,
      fatTargetG: fatTarget,
      proteinMinG: proteinMin,
      proteinMaxG: proteinMax,
      carbohydrateMinG: carbMin,
      carbohydrateMaxG: carbMax,
      fatMinG: fatMin,
      fatMaxG: fatMax,
    );
  }

  int get dailyCalorieTarget => nutritionTarget.calories;

  Map<String, dynamic> toJson() => {
    'name': name,
    'email': email,
    'age': age,
    'height_cm': heightCm,
    'weight_kg': weightKg,
    'target_weight_kg': targetWeightKg,
    'target_days': targetDays,
    'gender': gender,
    'activity': activity,
    'goal': goal,
    'allergies': allergies,
    'medical_conditions': medicalConditions,
  };

  @override
  bool operator ==(Object other) {
    return other is UserProfile &&
        name == other.name &&
        email == other.email &&
        age == other.age &&
        heightCm == other.heightCm &&
        weightKg == other.weightKg &&
        targetWeightKg == other.targetWeightKg &&
        targetDays == other.targetDays &&
        gender == other.gender &&
        activity == other.activity &&
        goal == other.goal &&
        listEquals(allergies, other.allergies) &&
        listEquals(medicalConditions, other.medicalConditions);
  }

  @override
  int get hashCode => Object.hashAll([
    name,
    email,
    age,
    heightCm,
    weightKg,
    targetWeightKg,
    targetDays,
    gender,
    activity,
    goal,
    ...allergies,
    ...medicalConditions,
  ]);
}

class NutritionTarget {
  const NutritionTarget({
    required this.maintenanceCalories,
    required this.calories,
    required this.proteinTargetG,
    required this.carbohydrateTargetG,
    required this.fatTargetG,
    required this.proteinMinG,
    required this.proteinMaxG,
    required this.carbohydrateMinG,
    required this.carbohydrateMaxG,
    required this.fatMinG,
    required this.fatMaxG,
  });

  final int maintenanceCalories;
  final int calories;
  final double proteinTargetG;
  final double carbohydrateTargetG;
  final double fatTargetG;
  final double proteinMinG;
  final double proteinMaxG;
  final double carbohydrateMinG;
  final double carbohydrateMaxG;
  final double fatMinG;
  final double fatMaxG;
}

int _intValue(Object? value, int fallback) => switch (value) {
  final num number => number.round(),
  _ => fallback,
};

List<String> _stringList(Object? value) => switch (value) {
  final List<Object?> values => values.whereType<String>().toList(),
  _ => const [],
};
