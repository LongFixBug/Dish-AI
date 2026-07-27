/// Vẽ linh vật hải ly Balance bằng vector, từng bộ phận rời nhau.
///
/// Bản trước dùng ảnh PNG rồi cắt hai cánh tay ra để xoay. Cắt tới chân thì
/// tắc: trong ảnh, hai bàn chân dính liền vào thân, không có nét mực nào ngăn.
/// Không có chân rời thì không có nhịp bước, và cả chuyển động chỉ còn là nhún
/// người với bóp ảnh. Vẽ bằng đường path thì mọi bộ phận đều là một mảnh riêng
/// — tai vẫy được, đuôi quét được, chân bước được, mắt chớp được.
library;

import 'dart:math';

import 'package:balance/features/mascot/domain/mascot_pose.dart';
import 'package:balance/features/mascot/domain/mascot_shape.dart';
import 'package:flutter/material.dart';

/// Bảng màu lấy từ bản vẽ gốc của linh vật.
abstract final class _Fur {
  static const outline = Color(0xFF241A13);
  static const coat = Color(0xFFD2762F);
  static const coatDark = Color(0xFFA85218);
  static const cream = Color(0xFFFAE7C8);
  static const creamLine = Color(0xFF9A6234);
  static const tail = Color(0xFF8C5734);
  static const tailDark = Color(0xFF66391F);
  static const nose = Color(0xFF4A2A18);
  static const vest = Color(0xFF4F91F7);
  static const badge = Color(0xFFFFD928);
  static const tooth = Color(0xFFFFFDF5);
  static const shine = Color(0xFFFFFFFF);
  static const shadow = Color(0xFF2C3E50);
}

/// Mọi số đo dưới đây nằm trong hộp vuông 100×100, mặt đất ở đáy hộp.
/// Vẽ theo tỉ lệ nên phóng to thu nhỏ cỡ nào cũng giữ nguyên dáng.
const double _design = 100;
const double _groundY = 98.6;

/// Bề dày nét mực. Vẽ nét trước rồi tô đè lên, nên nhìn thấy đúng một nửa.
const double _lineWidth = 5;

const double _headY = 31;
const double _headRy = 23;

/// Đáy thân luôn nằm ở đây, dáng nào cũng vậy — người tròn hơn thì phình lên
/// trên chứ không thụt xuống dưới, nếu không thì chân dài ngắn theo cân nặng.
const double _bodyBottom = 84;
const double _hipY = 75;
const double _legLength = 18;

/// Linh vật ở một tư thế cụ thể.
///
/// Bản thân lớp này không biết gì về thời gian: đưa [pose] nào thì vẽ đúng
/// khung hình đó. Nhờ vậy chụp lại được một khung bất kỳ để đối chiếu.
class MascotPainter extends CustomPainter {
  const MascotPainter({required this.pose, required this.shape});

  final MascotPose pose;
  final MascotShape shape;

  double get _plump => plumpnessFor(shape);

  double get _headRx => 23 + 3.5 * _plump;
  double get _bodyRx => 23 + 11 * _plump;
  double get _bodyRy => 21.5 + 3 * _plump;
  double get _bodyY => _bodyBottom - _bodyRy;
  double get _bellyRx => 14.5 + 6.5 * _plump;
  double get _legSpread => 9 + 4.5 * _plump;

  @override
  void paint(Canvas canvas, Size size) {
    final scale = min(size.width, size.height) / _design;
    canvas.save();
    canvas.translate(size.width / 2, size.height);
    canvas.scale(scale);
    canvas.translate(-_design / 2, -_design);

    _paintShadow(canvas);

    canvas.save();
    // Cú bật người lúc quay đầu nhấc cả nhân vật lên, bóng ở lại dưới đất.
    canvas.translate(0, -pose.hop * _design);
    // Xoay người: bóp bề ngang rồi bung ra phía bên kia.
    canvas.translate(_design / 2, 0);
    canvas.scale(pose.facing, 1);
    canvas.translate(-_design / 2, 0);

    // Chân vẽ trước để thân che mất phần đùi — chỉ còn bàn chân thò ra dưới
    // bụng, đúng kiểu nhân vật mập lùn.
    _paintLeg(canvas, -1, pose.leftLeg, _sideColor);
    _paintLeg(canvas, 1, pose.rightLeg, _Fur.coat);

    canvas.save();
    // Thân nhún trên hai chân đang bám đất, tâm xoay đặt ở hông.
    canvas.translate(0, -pose.bob * _design);
    canvas.translate(_design / 2, _hipY);
    canvas.rotate(pose.lean);
    canvas.scale(1, pose.squash);
    canvas.translate(-_design / 2, -_hipY);

    _paintTail(canvas);
    _paintArm(canvas, -1, pose.leftArm, _sideColor);
    _paintEars(canvas);
    _paintSilhouette(canvas);
    _paintCream(canvas);
    _paintVest(canvas);
    _paintFace(canvas);
    _paintArm(canvas, 1, pose.rightArm, _Fur.coat);

    canvas.restore();
    canvas.restore();
    canvas.restore();
  }

  /// Màu cho tay/chân phía xa: tối hơn một chút để có chiều sâu.
  Color get _sideColor => Color.lerp(_Fur.coat, _Fur.coatDark, 0.5)!;

  double get _headOffset => pose.headBob * _design;

  // ---------------------------------------------------------------- bóng đổ

  void _paintShadow(Canvas canvas) {
    // Bật càng cao thì bóng càng nhỏ và càng nhạt. Thiếu nó thì cú nhảy trông
    // như nhân vật bị kéo lên chứ không phải tự rời mặt đất.
    final near = (1 - pose.hop * 3.4).clamp(0.3, 1.0);
    canvas.drawOval(
      Rect.fromCenter(
        center: const Offset(_design / 2, _groundY + 0.8),
        width: 48 * near,
        height: 10 * near,
      ),
      Paint()..color = _Fur.shadow.withValues(alpha: 0.17 * near),
    );
  }

  // -------------------------------------------------------------------- đuôi

  void _paintTail(Canvas canvas) {
    canvas.save();
    canvas.translate(_design / 2 - _bodyRx * 0.66, 68);
    canvas.rotate(pose.tailSway);

    final tail = Path()
      ..moveTo(3, -8)
      ..cubicTo(-9, -9, -20, 0, -23, 12)
      ..cubicTo(-26, 24, -17, 31, -8, 26)
      ..cubicTo(-1, 22, 4, 9, 3, -8)
      ..close();
    _outlined(canvas, tail, _Fur.tail);

    // Vảy đuôi hải ly: hai chùm nét chéo cắt nhau, xén gọn trong lòng đuôi.
    canvas.save();
    canvas.clipPath(tail);
    final hatch = Paint()
      ..color = _Fur.tailDark.withValues(alpha: 0.55)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    for (var i = -34; i <= 16; i += 7) {
      final x = i.toDouble();
      canvas.drawLine(Offset(x, -14), Offset(x + 30, 34), hatch);
      canvas.drawLine(Offset(x, 34), Offset(x + 30, -14), hatch);
    }
    canvas.restore();
    canvas.restore();
  }

  // --------------------------------------------------------------------- tai

  void _paintEars(Canvas canvas) {
    for (final side in const [-1.0, 1.0]) {
      canvas.save();
      canvas.translate(_design / 2 + side * _headRx * 0.44, 20 + _headOffset);
      // Hai tai vẫy ngược chiều nhau cho khỏi trông như một khối cứng.
      canvas.rotate(-side * pose.earFlap);

      final centre = Offset(side * _headRx * 0.36, -6);
      final ear = Path()
        ..addOval(Rect.fromCircle(center: centre, radius: 7.2));
      _outlined(canvas, ear, _Fur.coat);
      canvas.drawOval(
        Rect.fromCenter(
          center: centre.translate(side * 1.6, 0.6),
          width: 6,
          height: 6.6,
        ),
        Paint()..color = _Fur.coatDark,
      );
      canvas.restore();
    }
  }

  // ------------------------------------------------------------ thân và đầu

  /// Đầu, thân và túm tóc gộp thành MỘT đường bao duy nhất.
  ///
  /// Vẽ rời từng khối thì chỗ đầu chồng lên thân sẽ hiện một cung mực thừa,
  /// nhìn ra ngay là hai mảnh dán lên nhau. Hợp path lại thì chỉ còn một
  /// silhouette liền mạch như bản vẽ gốc.
  Path _silhouette() {
    final head = Path()
      ..addOval(
        Rect.fromCenter(
          center: Offset(_design / 2, _headY + _headOffset),
          width: _headRx * 2,
          height: _headRy * 2,
        ),
      );
    final tuft = Path()
      ..moveTo(41, 14 + _headOffset)
      ..cubicTo(
        40,
        3 + _headOffset,
        52,
        -1 + _headOffset,
        58,
        4 + _headOffset,
      )
      ..cubicTo(
        53,
        4 + _headOffset,
        48,
        8 + _headOffset,
        47,
        15 + _headOffset,
      )
      ..close();
    final body = Path()
      ..addOval(
        Rect.fromCenter(
          center: Offset(_design / 2, _bodyY),
          width: _bodyRx * 2,
          height: _bodyRy * 2,
        ),
      );

    return Path.combine(
      PathOperation.union,
      Path.combine(PathOperation.union, body, head),
      tuft,
    );
  }

  void _paintSilhouette(Canvas canvas) =>
      _outlined(canvas, _silhouette(), _Fur.coat);

  /// Mảng lông sáng chạy liền từ mõm xuống bụng, đúng như bản vẽ gốc.
  void _paintCream(Canvas canvas) {
    final muzzle = Path()
      ..addOval(
        Rect.fromCenter(
          center: Offset(_design / 2, 40 + _headOffset),
          width: 36,
          height: 24,
        ),
      );
    final belly = Path()
      ..addOval(
        Rect.fromCenter(
          center: const Offset(_design / 2, 63),
          width: _bellyRx * 2,
          height: 40,
        ),
      );
    final cream = Path.combine(PathOperation.union, muzzle, belly);
    _outlined(canvas, cream, _Fur.cream, line: _Fur.creamLine, width: 2);
  }

  // -------------------------------------------------------------------- áo

  /// Áo gi-lê hai vạt, hở giữa để lộ mảng lông sáng.
  ///
  /// Vẽ vạt áo rộng quá khổ rồi XÉN theo đúng đường bao cơ thể. Cắt sẵn cho
  /// vừa thì mỗi dáng người lại phải chỉnh tay một bản; xén thì áo tự ôm lấy
  /// người gầy hay người tròn đều khít, mà viền mực của thân vẫn còn nguyên.
  void _paintVest(Canvas canvas) {
    final fit = _bodyRx / 28.5;

    canvas.save();
    canvas.clipPath(_silhouette());
    canvas.translate(_design / 2, 0);
    canvas.scale(fit, 1);
    canvas.translate(-_design / 2, 0);
    for (final side in const [-1.0, 1.0]) {
      canvas.save();
      canvas.translate(_design / 2, 0);
      canvas.scale(side, 1);
      canvas.translate(-_design / 2, 0);
      _outlined(canvas, _vestPanel(), _Fur.vest);
      canvas.restore();
    }
    canvas.restore();

    // Huy hiệu vẽ NGOÀI phép co ngang, nếu không thì người tròn hơn sẽ có
    // huy hiệu méo thành bầu dục.
    final centre = Offset(_design / 2 + 18.5 * fit, 68);
    _outlined(
      canvas,
      Path()..addOval(Rect.fromCircle(center: centre, radius: 5.9)),
      _Fur.badge,
      width: 3.4,
    );
    _paintLetterB(canvas, centre);
  }

  Path _vestPanel() => Path()
    ..moveTo(55, 51)
    ..cubicTo(62, 56.5, 69, 56, 74.5, 50)
    ..cubicTo(84, 59, 89, 74, 85, 92)
    ..cubicTo(76, 95, 67, 91, 62, 82)
    ..cubicTo(62.5, 71, 58, 60, 55, 51)
    ..close();

  void _paintLetterB(Canvas canvas, Offset centre) {
    final ink = Paint()
      ..color = _Fur.outline
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.7
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final x = centre.dx - 2.2;
    final top = centre.dy - 3.6;
    final mid = centre.dy;
    final bottom = centre.dy + 3.6;

    canvas.drawLine(Offset(x, top), Offset(x, bottom), ink);
    canvas.drawPath(
      Path()
        ..moveTo(x, top)
        ..cubicTo(x + 4.4, top, x + 4.4, mid, x, mid),
      ink,
    );
    canvas.drawPath(
      Path()
        ..moveTo(x, mid)
        ..cubicTo(x + 5, mid, x + 5, bottom, x, bottom),
      ink,
    );
  }

  // -------------------------------------------------------------------- mặt

  void _paintFace(Canvas canvas) {
    canvas.save();
    canvas.translate(_design / 2, 52 + _headOffset);
    canvas.rotate(pose.headTilt);
    canvas.translate(-_design / 2, -52);

    _paintEye(canvas, 39.8, 23);
    _paintEye(canvas, 60.2, 23);
    _paintNose(canvas);
    _paintMouth(canvas);
    _paintTeeth(canvas);

    canvas.restore();
  }

  void _paintEye(Canvas canvas, double x, double y) {
    // Nhắm mắt không xoá con ngươi mà bóp dẹt nó lại: còn một vệt mực mảnh,
    // đúng như mí mắt khép trong tranh vẽ tay.
    final open = pose.eyeOpen;
    final height = 1.6 + 10.8 * open;
    canvas.drawOval(
      Rect.fromCenter(center: Offset(x, y), width: 10, height: height),
      Paint()..color = _Fur.outline,
    );
    if (open > 0.35) {
      canvas.drawCircle(
        Offset(x - 1.9, y - 2.2),
        2.2,
        Paint()..color = _Fur.shine.withValues(alpha: (open - 0.35) / 0.65),
      );
    }
  }

  void _paintNose(Canvas canvas) {
    final nose = Path()
      ..moveTo(44.6, 32)
      ..cubicTo(45.4, 29.4, 54.6, 29.4, 55.4, 32)
      ..cubicTo(56.1, 35.4, 52.5, 38.4, 50, 38.4)
      ..cubicTo(47.5, 38.4, 43.9, 35.4, 44.6, 32)
      ..close();
    _outlined(canvas, nose, _Fur.nose, width: 2.6);
  }

  void _paintMouth(Canvas canvas) {
    final ink = Paint()
      ..color = _Fur.outline
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.6
      ..strokeCap = StrokeCap.round;
    canvas.drawPath(
      Path()
        ..moveTo(50, 38.4)
        ..quadraticBezierTo(43.8, 45.8, 36.4, 40.6),
      ink,
    );
    canvas.drawPath(
      Path()
        ..moveTo(50, 38.4)
        ..quadraticBezierTo(56.2, 45.8, 63.6, 40.6),
      ink,
    );
  }

  /// Hai cái răng cửa — thứ khiến người ta nhận ra ngay đây là con hải ly.
  void _paintTeeth(Canvas canvas) {
    final teeth = Path()
      ..addRRect(
        RRect.fromRectAndCorners(
          Rect.fromCenter(
            center: const Offset(_design / 2, 45.4),
            width: 10.6,
            height: 11.4,
          ),
          topLeft: const Radius.circular(1.6),
          topRight: const Radius.circular(1.6),
          bottomLeft: const Radius.circular(3.6),
          bottomRight: const Radius.circular(3.6),
        ),
      );
    _outlined(canvas, teeth, _Fur.tooth, width: 2.8);
    canvas.drawLine(
      const Offset(_design / 2, 40.2),
      const Offset(_design / 2, 50.6),
      Paint()
        ..color = _Fur.outline
        ..strokeWidth = 1.5,
    );
  }

  // ------------------------------------------------------------ tay và chân

  /// Góc nghỉ của tay so với phương thẳng đứng: buông xuôi và hơi xoè ra.
  static const _armRest = 0.62;

  void _paintArm(Canvas canvas, double side, double angle, Color colour) {
    canvas.save();
    canvas.translate(_design / 2 + side * _bodyRx * 0.78, 54);
    // Vẽ cánh tay chúc thẳng xuống rồi mới quay ra. Hai tay soi gương nhau nên
    // góc nghỉ đối dấu, còn cú vung tới trước thì cùng dấu cho cả hai.
    canvas.rotate(-side * _armRest - angle);

    final upper = Path()
      ..addRRect(
        RRect.fromRectXY(const Rect.fromLTWH(-5.2, -5.2, 10.4, 18), 5.2, 5.2),
      );
    final paw = Path()
      ..addOval(Rect.fromCircle(center: const Offset(0.4, 14), radius: 6.6));
    _outlined(canvas, Path.combine(PathOperation.union, upper, paw), colour);
    canvas.restore();
  }

  void _paintLeg(Canvas canvas, double side, LegPose leg, Color colour) {
    canvas.save();
    canvas.translate(_design / 2 + side * _legSpread, _hipY);
    canvas.rotate(leg.swing * 0.3);

    // Co chân lên là RÚT NGẮN ống chân chứ không nhấc cả hông: hông mà nhảy
    // theo thì thân cũng giật lên, hỏng luôn nhịp nhún.
    final length = _legLength - leg.lift * 7;
    final shin = Path()
      ..addRRect(
        RRect.fromRectXY(Rect.fromLTWH(-5, -7, 10, length + 7), 5, 5),
      );
    final foot = Path()
      ..addOval(
        Rect.fromCenter(
          center: Offset(2, length),
          width: 17,
          height: 10.4,
        ),
      );
    _outlined(canvas, Path.combine(PathOperation.union, shin, foot), colour);
    canvas.restore();
  }

  // ----------------------------------------------------------------- tiện ích

  /// Viền trước, tô sau. Nét nằm giữa đường bao nên bị phần tô che mất nửa
  /// trong — kết quả là một viền đều tăm tắp mà không phải vẽ hai đường path.
  void _outlined(
    Canvas canvas,
    Path path,
    Color fill, {
    Color? line,
    double width = _lineWidth,
  }) {
    canvas.drawPath(
      path,
      Paint()
        ..color = line ?? _Fur.outline
        ..style = PaintingStyle.stroke
        ..strokeWidth = width
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawPath(path, Paint()..color = fill);
  }

  @override
  bool shouldRepaint(MascotPainter oldDelegate) =>
      oldDelegate.shape != shape || oldDelegate.pose != pose;
}
