import 'dart:math';

import 'package:balance/features/journal/domain/sticker_physics.dart';
import 'package:flutter_test/flutter_test.dart';

/// Chạy mô phỏng bằng bước thời gian cố định, giống hệt widget chạy thật.
void settle(StickerWorld world, {int steps = 900}) {
  for (var i = 0; i < steps; i++) {
    world.step(1 / 60);
  }
}

void main() {
  group('rơi và chạm đáy', () {
    test('sticker rơi xuống rồi nằm yên trên đáy khung', () {
      final world = buildStickerWorld(
        count: 1,
        seed: 1,
        width: 300,
        height: 200,
        stickerSize: 60,
      );

      settle(world);

      final body = world.bodies.single;
      expect(body.y + body.radius, closeTo(200, 1));
      expect(body.vy.abs(), lessThan(6));
    });

    test('chưa tới lượt thả thì còn treo trên nóc khung', () {
      final world = buildStickerWorld(
        count: 3,
        seed: 1,
        width: 300,
        height: 200,
        stickerSize: 50,
        dropInterval: 1,
      );

      world.step(1 / 60);

      // Cái thứ hai hẹn thả ở giây thứ 1, mới trôi 1/60 giây nên chưa động đậy.
      expect(world.bodies[1].y, lessThan(0));
      expect(world.bodies[1].vy, 0);
    });
  });

  group('va chạm', () {
    test('hai sticker không chồng lên nhau sau khi đống nằm yên', () {
      final world = buildStickerWorld(
        count: 6,
        seed: 7,
        width: 200,
        height: 260,
        stickerSize: 56,
      );

      settle(world);

      for (var i = 0; i < world.bodies.length; i++) {
        for (var j = i + 1; j < world.bodies.length; j++) {
          final a = world.bodies[i];
          final b = world.bodies[j];
          final distance = sqrt(pow(b.x - a.x, 2) + pow(b.y - a.y, 2));
          // Cho phép lệch nhỏ do bước thời gian rời rạc.
          expect(distance, greaterThan(a.radius + b.radius - 2));
        }
      }
    });

    test('rơi trúng nhau thì lăn sang bên chứ không xếp thành cột', () {
      // Ba sticker thả đúng một cột: nếu không có va chạm ngang thì cả ba
      // giữ nguyên x, chồng thành tháp — thứ trông rất giả.
      final world = StickerWorld(
        bodies: [
          for (var i = 0; i < 3; i++)
            StickerBody(
              x: 100,
              y: -30.0 - i * 70,
              radius: 30,
              spawnAt: i * 0.15,
            ),
        ],
        width: 200,
        height: 200,
      );

      settle(world);

      final spread = world.bodies.map((body) => body.x).toList()..sort();
      expect(spread.last - spread.first, greaterThan(20));
    });

    test('không sticker nào lọt ra ngoài khung', () {
      final world = buildStickerWorld(
        count: 12,
        seed: 3,
        width: 240,
        height: 180,
        stickerSize: 52,
      );

      settle(world);

      for (final body in world.bodies) {
        expect(body.left, greaterThanOrEqualTo(-1));
        expect(body.left + body.size, lessThanOrEqualTo(241));
        expect(body.top + body.size, lessThanOrEqualTo(181));
      }
    });
  });

  group('tái lập và dừng', () {
    test('cùng seed cho đúng một đống — vào lại trang không xáo trộn', () {
      List<String> run() {
        final world = buildStickerWorld(
          count: 8,
          seed: 202607,
          width: 300,
          height: 190,
          stickerSize: 58,
        );
        settle(world);
        return world.bodies
            .map((b) => '${b.x.toStringAsFixed(4)},${b.y.toStringAsFixed(4)}')
            .toList();
      }

      expect(run(), run());
    });

    test('đống nằm yên thì báo settled để widget ngừng vẽ lại', () {
      final world = buildStickerWorld(
        count: 4,
        seed: 11,
        width: 260,
        height: 180,
        stickerSize: 54,
      );

      expect(world.isSettled, isFalse);
      settle(world);

      expect(world.isSettled, isTrue);
    });
  });
}
