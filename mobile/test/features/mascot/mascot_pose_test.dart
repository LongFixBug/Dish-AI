import 'package:balance/features/mascot/domain/mascot_pose.dart';
import 'package:flutter_test/flutter_test.dart';

/// Lấy mẫu dày đặc một vòng đi, dùng chung cho các phép kiểm toàn vòng.
Iterable<MascotPose> _lap({int samples = 400}) sync* {
  for (var i = 0; i < samples; i++) {
    yield mascotPoseAt(i / samples);
  }
}

void main() {
  group('đường đi', () {
    test('nửa vòng đầu đi sang phải, nửa sau quay về chỗ cũ', () {
      expect(mascotPoseAt(0).travel, closeTo(0, 0.001));
      expect(mascotPoseAt(0.45).travel, closeTo(1, 0.001));
      expect(mascotPoseAt(0.5).travel, closeTo(1, 0.001));
      expect(mascotPoseAt(0.95).travel, closeTo(0, 0.001));
    });

    test('không bao giờ đi lố ra ngoài dải', () {
      for (final pose in _lap()) {
        expect(pose.travel, inInclusiveRange(0, 1));
      }
    });

    test('pha ngoài khoảng 0..1 được gói lại chứ không văng ra', () {
      expect(mascotPoseAt(1.2).travel, closeTo(mascotPoseAt(0.2).travel, 1e-9));
      expect(
        mascotPoseAt(-0.7).travel,
        closeTo(mascotPoseAt(0.3).travel, 1e-9),
      );
    });
  });

  group('nhịp chân', () {
    test('hai chân luôn so le: chân này nhấc thì chân kia trụ', () {
      for (final pose in _lap()) {
        final bothUp = pose.leftLeg.lift > 0.1 && pose.rightLeg.lift > 0.1;
        // Trừ lúc bật người quay đầu — nhảy thì co cả hai chân là đúng.
        if (pose.hop > 0.001) continue;
        expect(bothUp, isFalse);
      }
    });

    test('lúc đi, chân trái và chân phải đưa ngược chiều nhau', () {
      final pose = mascotPoseAt(kMascotRestPhase);
      expect(pose.leftLeg.swing, closeTo(-pose.rightLeg.swing, 1e-9));
      expect(pose.leftLeg.swing.abs(), greaterThan(0.5));
    });

    test('tay đánh ngược chiều chân cùng bên', () {
      for (final pose in _lap()) {
        if (pose.hop > 0.001) continue;
        expect(pose.leftLeg.swing * pose.leftArm, lessThanOrEqualTo(1e-12));
        expect(pose.rightLeg.swing * pose.rightArm, lessThanOrEqualTo(1e-12));
      }
    });

    test('đi chậm thì bước chậm — nhịp chân bám quãng đường, không bám đồng hồ', () {
      const step = 0.004;
      double moved(double from) =>
          (mascotPoseAt(from + step).travel - mascotPoseAt(from).travel).abs();
      double stepped(double from) =>
          (mascotPoseAt(from + step).leftLeg.swing -
                  mascotPoseAt(from).leftLeg.swing)
              .abs();

      // Lúc vừa cất bước, người gần như chưa nhích khỏi chỗ cũ.
      expect(moved(0), lessThan(moved(0.2) / 5));
      // Thì chân cũng phải gần như chưa nhấc. Nếu nhịp chân bám đồng hồ, hai
      // con số này xấp xỉ nhau — nghĩa là đang guồng chân tại chỗ, bàn chân
      // trượt trên đất như đi trên băng.
      expect(stepped(0), lessThan(stepped(0.2) / 3));
    });

    test('trong lúc quay đầu thì đứng nguyên một chỗ', () {
      expect(mascotPoseAt(0.43).travel, closeTo(mascotPoseAt(0.46).travel, 1e-9));
    });
  });

  group('quay đầu', () {
    test('hết lượt đi là đổi hướng, và đổi hẳn chứ không lấp lửng', () {
      expect(mascotPoseAt(0.2).facing, closeTo(1, 1e-9));
      expect(mascotPoseAt(0.7).facing, closeTo(-1, 1e-9));
    });

    test('bật người rồi mới xoay, không xoay tại chỗ như lật ảnh', () {
      final mid = mascotPoseAt(_walkEnd + 0.045);
      expect(mid.hop, greaterThan(0.1));
      // Giữa cú xoay, người bóp gần hết bề ngang — đúng lúc đang quay lưng.
      expect(mid.facing.abs(), lessThan(0.1));
    });

    test('vào và ra khỏi cú quay đầu đều liền mạch với lúc đang đi', () {
      // Chỗ dễ sinh giật nhất: khung hình cuối của lượt đi và khung hình đầu
      // của cú nhảy phải gần như trùng nhau.
      final before = mascotPoseAt(_walkEnd - 1e-5);
      final after = mascotPoseAt(_walkEnd + 1e-5);
      expect(after.hop, lessThan(0.001));
      expect(after.leftLeg.swing, closeTo(before.leftLeg.swing, 0.01));
      expect(after.leftLeg.lift, closeTo(before.leftLeg.lift, 0.01));
      expect(after.leftArm, closeTo(before.leftArm, 0.01));
      expect(after.squash, closeTo(before.squash, 0.01));
      expect(after.facing, closeTo(before.facing, 0.01));
    });

    test('chỉ rời mặt đất trong lúc quay đầu', () {
      expect(mascotPoseAt(0.2).hop, 0);
      expect(mascotPoseAt(0.7).hop, 0);
    });
  });

  group('sự sống', () {
    test('mỗi vòng có chớp mắt, và phần lớn thời gian mắt vẫn mở', () {
      final poses = _lap(samples: 1000).toList();
      final closed = poses.where((pose) => pose.eyeOpen < 0.2).length;
      expect(closed, greaterThan(0), reason: 'không chớp mắt lần nào');
      expect(closed / poses.length, lessThan(0.1), reason: 'chớp quá nhiều');
    });

    test('thân luôn nhún trong biên độ hợp lý, không bẹp dí cũng không kéo dài', () {
      for (final pose in _lap()) {
        expect(pose.squash, inInclusiveRange(0.9, 1.12));
        expect(pose.bob, inInclusiveRange(0, 0.05));
        expect(pose.lean.abs(), lessThan(0.2));
      }
    });

    test('không có cú giật nào giữa hai khung hình liền nhau', () {
      // Mỗi bước lấy mẫu ở đây tương đương chưa tới một khung hình 60fps của
      // vòng 11 giây. Nhảy số quá lớn trong khoảng đó là giật thấy bằng mắt.
      var previous = mascotPoseAt(0);
      for (var i = 1; i <= 2000; i++) {
        final pose = mascotPoseAt(i / 2000);
        expect(
          (pose.travel - previous.travel).abs(),
          lessThan(0.01),
          reason: 'vị trí nhảy cóc tại pha ${i / 2000}',
        );
        expect(
          (pose.facing - previous.facing).abs(),
          lessThan(0.1),
          reason: 'hướng mặt lật đột ngột tại pha ${i / 2000}',
        );
        expect(
          (pose.hop - previous.hop).abs(),
          lessThan(0.02),
          reason: 'độ cao nhảy cóc tại pha ${i / 2000}',
        );
        previous = pose;
      }
    });
  });
}

/// Mốc kết thúc lượt đi thứ nhất, ngay trước khi quay đầu.
const double _walkEnd = 0.41;
