import 'package:balance/features/onboarding/domain/goal_target_rules.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('targetWeightError', () {
    test('tăng cân phải chọn số lớn hơn cân nặng hiện tại', () {
      expect(
        targetWeightError(goal: goalGain, weightKg: 65, targetWeightKg: 60),
        contains('lớn hơn 65 kg'),
      );
      expect(
        targetWeightError(goal: goalGain, weightKg: 65, targetWeightKg: 65),
        isNotNull,
        reason: 'bằng đúng cân nặng hiện tại thì không phải là tăng cân',
      );
      expect(
        targetWeightError(goal: goalGain, weightKg: 65, targetWeightKg: 70),
        isNull,
      );
    });

    test('giảm cân phải chọn số nhỏ hơn cân nặng hiện tại', () {
      expect(
        targetWeightError(goal: goalLose, weightKg: 65, targetWeightKg: 70),
        contains('nhỏ hơn 65 kg'),
      );
      expect(
        targetWeightError(goal: goalLose, weightKg: 65, targetWeightKg: 65),
        isNotNull,
      );
      expect(
        targetWeightError(goal: goalLose, weightKg: 65, targetWeightKg: 60),
        isNull,
      );
    });

    test('giữ cân không ràng buộc gì', () {
      expect(
        targetWeightError(goal: goalMaintain, weightKg: 65, targetWeightKg: 65),
        isNull,
      );
    });
  });

  group('targetWeightRange', () {
    test('chặn sẵn vùng mâu thuẫn ngay trên thước', () {
      expect(targetWeightRange(goal: goalGain, weightKg: 65).min, 66);
      expect(targetWeightRange(goal: goalLose, weightKg: 65).max, 64);
      final maintain = targetWeightRange(goal: goalMaintain, weightKg: 65);
      expect(maintain.min, 65);
      expect(maintain.max, 65);
    });

    test('không vượt biên cân nặng cho phép', () {
      expect(targetWeightRange(goal: goalGain, weightKg: 180).min, 180);
      expect(targetWeightRange(goal: goalLose, weightKg: 35).max, 35);
    });
  });

  group('suggestedTargetWeight', () {
    test('gợi ý lệch 5 kg đúng chiều mục tiêu', () {
      expect(suggestedTargetWeight(goal: goalGain, weightKg: 65), 70);
      expect(suggestedTargetWeight(goal: goalLose, weightKg: 65), 60);
      expect(suggestedTargetWeight(goal: goalMaintain, weightKg: 65), 65);
    });

    test('gợi ý luôn nằm trong khoảng hợp lệ', () {
      final heavy = suggestedTargetWeight(goal: goalGain, weightKg: 178);
      expect(heavy, lessThanOrEqualTo(maxBodyWeightKg));
      expect(heavy, greaterThan(178));
      final light = suggestedTargetWeight(goal: goalLose, weightKg: 37);
      expect(light, greaterThanOrEqualTo(minBodyWeightKg));
      expect(light, lessThan(37));
    });
  });

  group('isGoalStepComplete', () {
    test('chưa chọn mục tiêu thì chưa được đi tiếp', () {
      expect(
        isGoalStepComplete(goal: '', weightKg: 65, targetWeightKg: 70),
        isFalse,
      );
    });

    test('chọn rồi và số hợp lệ thì đi tiếp được', () {
      expect(
        isGoalStepComplete(goal: goalGain, weightKg: 65, targetWeightKg: 70),
        isTrue,
      );
      expect(
        isGoalStepComplete(goal: goalGain, weightKg: 65, targetWeightKg: 64),
        isFalse,
      );
    });
  });
}
