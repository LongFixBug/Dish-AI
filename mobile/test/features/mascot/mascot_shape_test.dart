import 'package:balance/features/mascot/domain/mascot_shape.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('bodyMassIndex', () {
    test('tính đúng công thức kg trên mét bình phương', () {
      // 65 kg, 1,70 m → 65 / 2,89 ≈ 22,49
      expect(
        bodyMassIndex(heightCm: 170, weightKg: 65),
        closeTo(22.49, 0.01),
      );
    });

    test('số liệu vô lý thì trả null thay vì chia bừa', () {
      expect(bodyMassIndex(heightCm: 0, weightKg: 65), isNull);
      expect(bodyMassIndex(heightCm: 170, weightKg: 0), isNull);
      expect(bodyMassIndex(heightCm: -170, weightKg: 65), isNull);
    });
  });

  group('mascotShapeFor', () {
    test('dưới 18,5 là dáng gầy', () {
      // 50 kg, 1,75 m → BMI ≈ 16,3
      expect(
        mascotShapeFor(heightCm: 175, weightKg: 50),
        MascotShape.slim,
      );
    });

    test('từ 18,5 đến dưới 23 là dáng cân đối', () {
      // 65 kg, 1,70 m → 22,49
      expect(mascotShapeFor(heightCm: 170, weightKg: 65), MascotShape.fit);
      // 54 kg, 1,70 m → 18,69, ngay trên ngưỡng dưới
      expect(mascotShapeFor(heightCm: 170, weightKg: 54), MascotShape.fit);
    });

    test('từ 23 trở lên là dáng tròn — ngưỡng WHO cho người châu Á', () {
      // 67 kg, 1,70 m → 23,18
      expect(mascotShapeFor(heightCm: 170, weightKg: 67), MascotShape.chubby);
      expect(mascotShapeFor(heightCm: 160, weightKg: 80), MascotShape.chubby);
    });

    test('thiếu dữ liệu thì về dáng cân đối, không phán bừa cơ thể ai', () {
      expect(mascotShapeFor(heightCm: 0, weightKg: 0), MascotShape.fit);
    });
  });

  group('plumpnessFor', () {
    test('trải đủ từ 0 tới 1 để nét vẽ đổi rõ giữa ba dáng', () {
      expect(plumpnessFor(MascotShape.slim), 0);
      expect(plumpnessFor(MascotShape.fit), 0.5);
      expect(plumpnessFor(MascotShape.chubby), 1);
    });
  });

  group('mascotCaptionFor', () {
    test('mỗi dáng một câu, và không câu nào chê bai cơ thể', () {
      final captions = MascotShape.values.map(mascotCaptionFor).toList();

      expect(captions.toSet(), hasLength(3));
      for (final caption in captions) {
        expect(caption, isNotEmpty);
        for (final harsh in ['béo', 'mập', 'ốm', 'thừa cân']) {
          expect(caption.toLowerCase(), isNot(contains(harsh)));
        }
      }
    });
  });
}
