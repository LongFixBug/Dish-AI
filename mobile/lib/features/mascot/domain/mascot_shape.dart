/// Chọn dáng cho linh vật thú mỏ vịt theo chỉ số cơ thể.
///
/// Tách khỏi widget để test được ngưỡng, và để chỗ nào cần cũng hỏi được cùng
/// một câu trả lời thay vì mỗi màn hình tự tính một kiểu.
library;

/// Ba dáng của linh vật.
enum MascotShape {
  /// Gầy — người dùng đang dưới mức cân nặng khoẻ mạnh.
  slim,

  /// Cân đối.
  fit,

  /// Tròn trịa.
  chubby,
}

/// BMI = cân nặng (kg) / bình phương chiều cao (m).
///
/// Trả ``null`` khi chiều cao vô lý: thà không nói gì còn hơn nói sai về cơ thể
/// người dùng.
double? bodyMassIndex({required int heightCm, required int weightKg}) {
  if (heightCm <= 0 || weightKg <= 0) return null;
  final metres = heightCm / 100;
  return weightKg / (metres * metres);
}

// Ngưỡng theo khuyến nghị của WHO cho người châu Á — thấp hơn ngưỡng quốc tế
// (25) vì cùng một BMI, người châu Á có tỉ lệ mỡ và rủi ro chuyển hoá cao hơn.
const double _slimBelow = 18.5;
const double _chubbyFrom = 23;

/// Dáng linh vật ứng với chỉ số cơ thể.
///
/// Thiếu dữ liệu thì trả [MascotShape.fit]: linh vật là thứ trang trí, không
/// được phép ám chỉ người dùng gầy hay béo khi chưa biết gì về họ.
MascotShape mascotShapeFor({required int heightCm, required int weightKg}) {
  final bmi = bodyMassIndex(heightCm: heightCm, weightKg: weightKg);
  if (bmi == null) return MascotShape.fit;
  if (bmi < _slimBelow) return MascotShape.slim;
  if (bmi >= _chubbyFrom) return MascotShape.chubby;
  return MascotShape.fit;
}

/// Độ "tròn" của thân, 0 = gầy nhất, 1 = tròn nhất. Dùng để vẽ.
double plumpnessFor(MascotShape shape) => switch (shape) {
  MascotShape.slim => 0,
  MascotShape.fit => 0.5,
  MascotShape.chubby => 1,
};

/// Câu nói kèm linh vật — nhẹ nhàng, không phán xét cơ thể ai.
String mascotCaptionFor(MascotShape shape) => switch (shape) {
  MascotShape.slim => 'Ăn thêm chút nữa nhé!',
  MascotShape.fit => 'Bạn đang cân đối lắm!',
  MascotShape.chubby => 'Mình cùng ăn cân bằng nào!',
};
