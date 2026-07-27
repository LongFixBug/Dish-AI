/// Mô phỏng vật lý cho đống sticker: rơi, va vào nhau, lăn ra chỗ trống.
///
/// Cố tình viết thuần Dart, không đụng widget: toàn bộ chuyển động test được
/// bằng unit test, và vì bước thời gian cố định + seed cố định nên cùng một
/// tháng luôn cho ra cùng một đống.
library;

import 'dart:math';

/// Một sticker trong mô phỏng, coi như đĩa tròn có khối lượng.
class StickerBody {
  StickerBody({
    required this.x,
    required this.y,
    required this.radius,
    required this.spawnAt,
    this.vx = 0,
    this.vy = 0,
    this.angle = 0,
    this.spin = 0,
    this.bias = 1,
  });

  /// Tâm sticker.
  double x;
  double y;
  double vx;
  double vy;
  double angle;

  /// Tốc độ xoay (radian/giây).
  double spin;
  final double radius;

  /// Giây kể từ lúc bắt đầu mới được thả rơi — để chúng rơi lần lượt.
  final double spawnAt;

  /// +1 hoặc -1, phá thế đối xứng khi hai sticker chồng đúng trục dọc.
  ///
  /// Vật lý thật cũng vướng chỗ này: hai quả bóng xếp thẳng hàng hoàn hảo thì
  /// pháp tuyến va chạm thuần đứng, không có lực ngang nào, nên chúng đứng
  /// thành tháp mãi. Một chút lệch cố định làm chúng đổ và lăn sang bên.
  final double bias;

  double get left => x - radius;
  double get top => y - radius;
  double get size => radius * 2;
}

/// Thế giới 2D chứa các sticker đang rơi.
class StickerWorld {
  StickerWorld({
    required this.bodies,
    required this.width,
    required this.height,
    this.gravity = 1500,
  });

  final List<StickerBody> bodies;
  final double width;
  final double height;
  final double gravity;

  double _elapsed = 0;

  /// Nảy lại bao nhiêu phần khi chạm đáy — thấp để đống mau nằm yên.
  static const _floorBounce = 0.24;
  static const _wallBounce = 0.4;

  /// Ma sát khi trượt trên đáy; cũng là thứ khiến sticker "lăn ra chỗ khác"
  /// thay vì dính nguyên chỗ chạm đất.
  static const _floorFriction = 0.86;

  /// Va giữa hai sticker: nảy nhẹ và đẩy nhau ra, đủ để chúng trượt sang bên
  /// rồi lấp vào chỗ trống chứ không chồng đúng lên nhau.
  static const _pairBounce = 0.3;

  static const _sleepSpeed = 6.0;

  double get elapsed => _elapsed;

  /// Mọi sticker đã thả và gần như đứng yên → có thể ngừng vẽ lại.
  bool get isSettled {
    for (final body in bodies) {
      if (body.spawnAt > _elapsed) return false;
      if (body.vx.abs() + body.vy.abs() > _sleepSpeed) return false;
      if (body.y + body.radius < height - 1) return false;
    }
    return true;
  }

  /// Số vòng giải va chạm mỗi khung.
  ///
  /// Một vòng là không đủ: tách cặp A-B xong có thể đẩy A lún vào C, và đống
  /// càng dày thì càng nhiều tầng cần gỡ. Lặp vài vòng rồi mới kẹp lại tường
  /// cho ra kết quả không còn chồng lấn.
  static const _solverIterations = 4;

  /// Tiến mô phỏng thêm [dt] giây.
  void step(double dt) {
    _elapsed += dt;
    for (final body in bodies) {
      if (body.spawnAt > _elapsed) continue;
      body.vy += gravity * dt;
      body.x += body.vx * dt;
      body.y += body.vy * dt;
      body.angle += body.spin * dt;
    }
    // Giải va chạm sau khi mọi vật đã dịch chuyển: làm xen kẽ trong vòng lặp
    // trên sẽ cho kết quả phụ thuộc thứ tự duyệt, mỗi khung một kiểu.
    for (var i = 0; i < _solverIterations; i++) {
      _collidePairs();
      // Kẹp lại tường SAU mỗi vòng: bước tách cặp có thể đẩy sticker xuyên
      // qua đáy, và nếu không kẹp lại thì nó rơi mất khỏi khung.
      for (final body in bodies) {
        if (body.spawnAt > _elapsed) continue;
        _collideWalls(body);
      }
    }
  }

  void _collideWalls(StickerBody body) {
    if (body.x - body.radius < 0) {
      body.x = body.radius;
      body.vx = -body.vx * _wallBounce;
      body.spin = -body.spin * 0.5;
    } else if (body.x + body.radius > width) {
      body.x = width - body.radius;
      body.vx = -body.vx * _wallBounce;
      body.spin = -body.spin * 0.5;
    }
    final floor = height - body.radius;
    if (body.y > floor) {
      body.y = floor;
      body.vy = -body.vy * _floorBounce;
      body.vx *= _floorFriction;
      // Chạm đất thì lăn theo hướng đang trượt.
      body.spin = body.vx / max(body.radius, 1) * 0.8;
      if (body.vy.abs() < 20) body.vy = 0;
    }
  }

  void _collidePairs() {
    for (var i = 0; i < bodies.length; i++) {
      final a = bodies[i];
      if (a.spawnAt > _elapsed) continue;
      for (var j = i + 1; j < bodies.length; j++) {
        final b = bodies[j];
        if (b.spawnAt > _elapsed) continue;
        var dx = b.x - a.x;
        var dy = b.y - a.y;
        var distance = sqrt(dx * dx + dy * dy);
        final minDistance = a.radius + b.radius;
        if (distance >= minDistance) continue;
        if (distance == 0) {
          // Chồng đúng tâm nhau: đẩy lệch một chút cho có phương để tách.
          dx = 0.01 * b.bias;
          dy = -0.01;
          distance = 0.0141;
        } else if (dx.abs() < minDistance * 0.06) {
          // Gần như thẳng trục dọc: chèn một chút lệch ngang, nếu không cả
          // chồng đứng yên thành tháp thay vì đổ ra.
          dx += minDistance * 0.05 * b.bias;
          distance = sqrt(dx * dx + dy * dy);
        }
        final nx = dx / distance;
        final ny = dy / distance;
        // Tách hết phần chồng lấn (mỗi bên một nửa) thay vì tách nửa vời:
        // tách thiếu thì trọng lực ép lại ngay khung sau và đống lún dần.
        final overlap = (minDistance - distance) / 2;
        a.x -= nx * overlap;
        a.y -= ny * overlap;
        b.x += nx * overlap;
        b.y += ny * overlap;

        // Trao đổi vận tốc theo phương pháp tuyến, hai vật coi như cùng khối.
        final relative = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
        if (relative > 0) continue;
        final impulse = -(1 + _pairBounce) * relative / 2;
        a.vx -= impulse * nx;
        a.vy -= impulse * ny;
        b.vx += impulse * nx;
        b.vy += impulse * ny;
        // Va chạm lệch tâm thì sinh xoay — đó là cái khiến đống nhìn "sống".
        a.spin -= impulse * 0.012;
        b.spin += impulse * 0.012;
      }
    }
  }
}

/// Dựng thế giới ban đầu: mọi sticker treo phía trên khung, thả lần lượt.
///
/// Cùng [seed] cho đúng một kịch bản rơi, nên vào lại trang thì đống lặp lại
/// y hệt thay vì bày ra một hình khác.
StickerWorld buildStickerWorld({
  required int count,
  required int seed,
  required double width,
  required double height,
  required double stickerSize,
  double dropInterval = 0.09,
}) {
  final random = Random(seed);
  final radius = stickerSize / 2;
  final bodies = <StickerBody>[];
  for (var i = 0; i < count; i++) {
    final x = radius + random.nextDouble() * max(width - stickerSize, 1);
    bodies.add(
      StickerBody(
        x: x,
        // Treo trên nóc khung, cách nhau ra để không sinh ra đã chồng lên nhau.
        y: -radius - i * stickerSize * 0.35,
        radius: radius,
        spawnAt: i * dropInterval,
        vx: (random.nextDouble() - 0.5) * 90,
        angle: (random.nextDouble() - 0.5) * 0.8,
        spin: (random.nextDouble() - 0.5) * 2.5,
        bias: i.isEven ? 1 : -1,
      ),
    );
  }
  return StickerWorld(bodies: bodies, width: width, height: height);
}
