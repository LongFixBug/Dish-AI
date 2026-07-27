/// Diễn xuất của linh vật: mỗi khoảnh khắc là một bộ góc và độ lệch.
///
/// Tách hẳn khỏi phần vẽ vì đây mới là thứ quyết định "trông có sống không".
/// Để lẫn trong `CustomPainter` thì không ai kiểm được nhịp bước hay lúc quay
/// đầu — chỉ còn cách mở app ra nhìn và đoán.
library;

import 'dart:math';

/// Tư thế một chân.
class LegPose {
  const LegPose({required this.swing, required this.lift});

  /// -1..1, dương là đưa chân về phía trước (cùng hướng đang đi).
  final double swing;

  /// 0..1, co chân lên khỏi mặt đất.
  final double lift;
}

/// Trọn một khung hình của linh vật — đủ số để vẽ ra, không thiếu thứ gì.
class MascotPose {
  const MascotPose({
    required this.travel,
    required this.facing,
    required this.hop,
    required this.bob,
    required this.squash,
    required this.lean,
    required this.leftLeg,
    required this.rightLeg,
    required this.leftArm,
    required this.rightArm,
    required this.headBob,
    required this.headTilt,
    required this.earFlap,
    required this.tailSway,
    required this.eyeOpen,
  });

  /// Vị trí trên dải đi: 0 là sát mép trái, 1 là sát mép phải.
  final double travel;

  /// Hướng mặt kèm bề ngang lúc xoay người. Dấu là hướng (dương là nhìn sang
  /// phải), trị tuyệt đối là phần bề ngang còn lại — bóp về 0,32 giữa cú xoay
  /// rồi bung ra phía bên kia, đúng kiểu nhân vật 2D quay lưng.
  final double facing;

  /// Cả người rời mặt đất, theo tỉ lệ chiều cao. Chỉ khác 0 lúc bật quay đầu.
  final double hop;

  /// Thân nhún lên xuống trong khi hai chân vẫn bám đất.
  final double bob;

  /// 1 là bình thường, nhỏ hơn là bẹt xuống, lớn hơn là vươn cao.
  final double squash;

  /// Nghiêng người, radian, dương là ngả sang phải.
  final double lean;

  final LegPose leftLeg;
  final LegPose rightLeg;

  /// Góc vung tay, radian, dương là hất ra phía trước.
  final double leftArm;
  final double rightArm;

  /// Đầu nhún trễ hơn thân một nhịp, theo tỉ lệ chiều cao.
  final double headBob;

  /// Nghiêng đầu, radian.
  final double headTilt;

  /// Tai vẫy, radian.
  final double earFlap;

  /// Đuôi quét ngang, radian.
  final double tailSway;

  /// 1 là mắt mở to, 0 là nhắm tịt.
  final double eyeOpen;
}

/// Số bước chân cho mỗi lượt băng ngang sân.
///
/// Lẻ 0,25 bước có chủ đích: hết lượt thì rơi đúng vào tư thế hai chân dang ra
/// cùng chạm đất, thay vì đứng khựng lại với một chân đang lơ lửng.
const double _stepsPerTrip = 6.25;

/// Phần của một vòng dành cho mỗi lần quay đầu.
const double _turnShare = 0.09;

/// Phần của một nửa vòng thật sự dùng để đi.
const double _walkShare = 0.5 - _turnShare;

/// Khúc giữa cú quay đầu dành cho việc xoay lưng, tính theo tỉ lệ cửa sổ đó.
const double _spinFrom = 0.35;
const double _spinTo = 0.65;

/// Khoảnh khắc trong vòng mà linh vật chớp mắt.
const List<double> _blinkMoments = [0.11, 0.29, 0.58, 0.83];

/// Một cái chớp mắt dài bao lâu, tính theo tỉ lệ vòng.
const double _blinkSpan = 0.016;

/// Pha dùng cho khung hình đứng yên (test, ảnh chụp duyệt mẫu).
///
/// Rơi vào giữa lượt đi, đúng lúc hai chân dang rộng nhất — nhìn một khung là
/// biết ngay nhân vật đang bước, chứ không phải đang đứng chôn chân.
const double kMascotRestPhase = 0.21;

/// Tư thế linh vật tại pha [phase] của vòng đi (0..1, ra ngoài thì gói lại).
///
/// Một vòng gồm: đi sang phải, bật người quay đầu, đi ngược về, quay lại chỗ cũ.
MascotPose mascotPoseAt(double phase) {
  final t = phase - phase.floorToDouble();
  final isReturning = t >= 0.5;
  final local = t - (isReturning ? 0.5 : 0.0);

  final isWalking = local < _walkShare;
  final walkT = isWalking ? local / _walkShare : 1.0;
  final turnT = isWalking ? 0.0 : (local - _walkShare) / _turnShare;

  // Tăng tốc từ lúc đứng yên rồi hãm dần trước khi quay đầu. Không có đoạn này
  // thì nhân vật khởi hành và dừng lại giật cục như bị tua.
  final eased = walkT * walkT * (3 - 2 * walkT);
  final distance = isReturning ? 1 - eased : eased;

  // Nhịp chân bám theo QUÃNG ĐƯỜNG chứ không theo thời gian: đi chậm thì bước
  // chậm, dừng thì chân dừng. Lấy theo thời gian là bàn chân trượt trên đất
  // như đi trên băng.
  final walked = isReturning ? 2 - distance : distance;
  final theta = walked * _stepsPerTrip * 2 * pi;
  final swing = sin(theta);
  final stance = cos(theta);

  // Chân nhấc cao nhất lúc đi ngang qua chân trụ, duỗi xa nhất lúc chạm đất —
  // lệch nhau đúng một phần tư nhịp, và đó là cả bí quyết của một chu kỳ đi.
  var leftLeg = LegPose(swing: swing, lift: max(0.0, stance));
  var rightLeg = LegPose(swing: -swing, lift: max(0.0, -stance));

  // Tay đánh ngược chiều chân, như người thật giữ thăng bằng.
  var leftArm = -swing * 0.42;
  var rightArm = swing * 0.42;

  // Người cao nhất lúc chân đi ngang qua nhau, thấp nhất lúc hai chân dang ra.
  var bob = 0.026 * stance.abs();
  var squash = 0.968 + 0.05 * swing.abs();

  // Lạch bạch: đổ người về phía chân đang trụ, cộng thêm chút chúi tới trước
  // theo tốc độ. Nhanh thì chúi nhiều, đứng lại thì đứng thẳng.
  final pace = (4 * walkT * (1 - walkT)).clamp(0.0, 1.0);
  var lean = 0.055 * stance * pace + 0.05 * pace;

  var headBob = 0.013 * cos(theta - 0.9);
  var headTilt = -lean * 0.4 + 0.03 * swing;
  var earFlap = 0.26 * sin(theta - 1.5);
  var tailSway = 0.2 * sin(theta - 0.8);

  var facing = isReturning ? -1.0 : 1.0;
  var hop = 0.0;

  if (!isWalking) {
    // Quay đầu = bật nhẹ lên rồi xoay người. Đứng yên xoay tại chỗ thì trông
    // như tấm hình bị lật, có cú nhảy mới ra chuyển động.
    final air = sin(pi * turnT);

    // Bề ngang thu về 0 rồi bung ra phía bên kia, KHÔNG chặn đáy. Chặn lại thì
    // đúng khoảnh khắc đổi dấu, nhân vật lật cái phựt từ hẹp bên này sang hẹp
    // bên kia — mắt bắt được ngay. Cho đi qua 0 thì chỉ mất một hai khung hình
    // mỏng như tờ giấy, và đó chính là cảm giác xoay lưng.
    //
    // Cú xoay dồn vào khúc giữa cú nhảy chứ không dàn đều cả cửa sổ quay đầu:
    // trải ra thì nhân vật dẹt như tờ giấy suốt hơn mười khung hình liền, thành
    // ra trông như bị bóp méo. Gọn lại vài khung thì đúng là một cái quay lưng,
    // và nó rơi trúng lúc người đang ở đỉnh cao nhất.
    final spinT = ((turnT - _spinFrom) / (_spinTo - _spinFrom)).clamp(0.0, 1.0);
    facing = (isReturning ? -1 : 1) * cos(pi * spinT);

    hop = 0.15 * air;

    // Pha vào tư thế nhảy theo chính độ cao: lúc vừa chớm rời đất thì vẫn là
    // dáng đang đi, càng lên cao mới càng co người lại. Thay thẳng tay thì
    // ngay khung hình đầu tiên của cú nhảy, hai chân đang dang rộng bị bập
    // vào nhau — một cú giật rõ mồn một.
    bob *= 1 - air;
    squash = _blend(squash, 1.07, air);
    lean = _blend(lean, 0.12, air);
    leftLeg = LegPose(
      swing: _blend(leftLeg.swing, 0.3, air),
      lift: _blend(leftLeg.lift, 0.8, air),
    );
    rightLeg = LegPose(
      swing: _blend(rightLeg.swing, -0.22, air),
      lift: _blend(rightLeg.lift, 0.62, air),
    );
    leftArm = _blend(leftArm, -0.8, air);
    rightArm = _blend(rightArm, -0.62, air);
    headBob = _blend(headBob, -0.012, air);
    headTilt = _blend(headTilt, 0.09, air);
    earFlap = _blend(earFlap, 0.55, air);
    tailSway = _blend(tailSway, 0.45, air);
  }

  return MascotPose(
    travel: distance,
    facing: facing,
    hop: hop,
    bob: bob,
    squash: squash,
    lean: lean,
    leftLeg: leftLeg,
    rightLeg: rightLeg,
    leftArm: leftArm,
    rightArm: rightArm,
    headBob: headBob,
    headTilt: headTilt,
    earFlap: earFlap,
    tailSway: tailSway,
    eyeOpen: _eyeOpenAt(t),
  );
}

/// Pha từ [from] sang [to] theo trọng số [weight] (0 giữ nguyên, 1 đổi hẳn).
double _blend(double from, double to, double weight) =>
    from + (to - from) * weight;

/// Độ mở mắt tại pha [t].
///
/// Chớp mắt là thứ rẻ nhất để một nhân vật thôi trông như hình dán: chỉ vài
/// khung hình nhắm lại, nhưng thiếu nó thì mắt trợn suốt hai mươi giây.
double _eyeOpenAt(double t) {
  for (final moment in _blinkMoments) {
    final distance = (t - moment).abs();
    if (distance < _blinkSpan) return distance / _blinkSpan;
  }
  return 1;
}
