import 'package:flutter/foundation.dart';

class UserProfile {
  const UserProfile({
    required this.name,
    required this.email,
    required this.age,
    required this.heightCm,
    required this.weightKg,
    required this.targetWeightKg,
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
  final String gender;
  final String activity;
  final String goal;
  final List<String> allergies;
  final List<String> medicalConditions;

  bool get hasNutritionSafetyFlags =>
      allergies.isNotEmpty || medicalConditions.isNotEmpty;

  int get dailyCalorieTarget {
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
    final goalOffset = switch (goal) {
      'Giảm cân' => -400.0,
      'Tăng cân' => 300.0,
      _ => 0.0,
    };
    final basal =
        (10 * weightKg) + (6.25 * heightCm) - (5 * age) + genderOffset;
    return (basal * activityFactor + goalOffset).round().clamp(1200, 4000);
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'email': email,
    'age': age,
    'height_cm': heightCm,
    'weight_kg': weightKg,
    'target_weight_kg': targetWeightKg,
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
    gender,
    activity,
    goal,
    ...allergies,
    ...medicalConditions,
  ]);
}

int _intValue(Object? value, int fallback) => switch (value) {
  final num number => number.round(),
  _ => fallback,
};

List<String> _stringList(Object? value) => switch (value) {
  final List<Object?> values => values.whereType<String>().toList(),
  _ => const [],
};
