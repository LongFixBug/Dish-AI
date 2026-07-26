import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('target duration changes the calorie target for weight loss', () {
    final short = _profile(targetDays: 45);
    final long = _profile(targetDays: 180);

    expect(short.dailyCalorieTarget, lessThan(long.dailyCalorieTarget));
  });

  test('macro targets use body weight and target calories', () {
    final light = _profile(weightKg: 55, targetWeightKg: 50);
    final heavy = _profile(weightKg: 90, targetWeightKg: 85);

    expect(
      heavy.nutritionTarget.proteinTargetG,
      greaterThan(light.nutritionTarget.proteinTargetG),
    );
    expect(
      heavy.nutritionTarget.calories,
      greaterThan(light.nutritionTarget.calories),
    );
  });

  test('maintain goal ignores an accidental target weight', () {
    final profile = _profile(goal: 'Giữ cân', weightKg: 70, targetWeightKg: 40);

    expect(
      profile.dailyCalorieTarget,
      profile.nutritionTarget.maintenanceCalories,
    );
  });
}

UserProfile _profile({
  int age = 30,
  int heightCm = 170,
  int weightKg = 70,
  int targetWeightKg = 65,
  int targetDays = 90,
  String goal = 'Giảm cân',
}) {
  return UserProfile(
    name: 'An',
    email: 'an@example.com',
    age: age,
    heightCm: heightCm,
    weightKg: weightKg,
    targetWeightKg: targetWeightKg,
    targetDays: targetDays,
    gender: 'Nam',
    activity: 'Vừa phải',
    goal: goal,
  );
}
