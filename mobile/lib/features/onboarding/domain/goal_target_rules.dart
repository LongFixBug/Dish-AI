/// Quy tắc ràng buộc giữa mục tiêu và cân nặng mong muốn.
///
/// Tách khỏi widget để test được bằng unit test: đây là phần dễ sai và dễ
/// thay đổi nhất của bước onboarding cuối.
library;

const String goalLose = 'Giảm cân';
const String goalMaintain = 'Giữ cân';
const String goalGain = 'Tăng cân';

/// Biên cân nặng app chấp nhận, khớp với ràng buộc của hồ sơ.
const int minBodyWeightKg = 35;
const int maxBodyWeightKg = 180;

/// Khoảng chênh gợi ý khi vừa chọn mục tiêu, để thước không nhảy về số vô lý.
const int _suggestedDeltaKg = 5;

/// Cân nặng mong muốn đề xuất ngay sau khi người dùng chọn mục tiêu.
int suggestedTargetWeight({required String goal, required int weightKg}) {
  final range = targetWeightRange(goal: goal, weightKg: weightKg);
  final suggested = switch (goal) {
    goalGain => weightKg + _suggestedDeltaKg,
    goalLose => weightKg - _suggestedDeltaKg,
    _ => weightKg,
  };
  return suggested.clamp(range.min, range.max);
}

/// Khoảng giá trị hợp lệ của thước cân nặng mong muốn.
///
/// Tăng cân thì thước bắt đầu từ trên cân nặng hiện tại một ký, giảm cân thì
/// dừng ở dưới một ký — người dùng không kéo được vào vùng mâu thuẫn ngay từ
/// đầu, thay vì kéo thoải mái rồi mới bị báo lỗi.
({int min, int max}) targetWeightRange({
  required String goal,
  required int weightKg,
}) {
  final current = weightKg.clamp(minBodyWeightKg, maxBodyWeightKg);
  return switch (goal) {
    goalGain => (
      min: (current + 1).clamp(minBodyWeightKg, maxBodyWeightKg),
      max: maxBodyWeightKg,
    ),
    goalLose => (
      min: minBodyWeightKg,
      max: (current - 1).clamp(minBodyWeightKg, maxBodyWeightKg),
    ),
    _ => (min: current, max: current),
  };
}

/// Thông báo lỗi khi cân nặng mong muốn mâu thuẫn với mục tiêu, `null` nếu hợp lệ.
String? targetWeightError({
  required String goal,
  required int weightKg,
  required int targetWeightKg,
}) {
  return switch (goal) {
    goalGain when targetWeightKg <= weightKg =>
      'Mục tiêu tăng cân cần cân nặng mong muốn lớn hơn $weightKg kg hiện tại.',
    goalLose when targetWeightKg >= weightKg =>
      'Mục tiêu giảm cân cần cân nặng mong muốn nhỏ hơn $weightKg kg hiện tại.',
    _ => null,
  };
}

/// Bước mục tiêu đã đủ điều kiện bấm "Hoàn tất" chưa.
bool isGoalStepComplete({
  required String goal,
  required int weightKg,
  required int targetWeightKg,
}) {
  if (goal.isEmpty) return false;
  return targetWeightError(
        goal: goal,
        weightKg: weightKg,
        targetWeightKg: targetWeightKg,
      ) ==
      null;
}
