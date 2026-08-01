@Tags(['golden'])
library;

import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/mascot/domain/mascot_pose.dart';
import 'package:balance/features/mascot/domain/mascot_shape.dart';
import 'package:balance/features/mascot/presentation/mascot_painter.dart';
import 'package:balance/features/mascot/presentation/walking_mascot.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/load_test_fonts.dart';

/// Bút vẽ mà widget đang thật sự dùng — nơi duy nhất biết tư thế hiện tại.
MascotPainter _painterIn(WidgetTester tester) => tester
    .widgetList<CustomPaint>(find.byType(CustomPaint))
    .map((paint) => paint.painter)
    .whereType<MascotPainter>()
    .single;

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    await loadBalanceTestFonts();
  });

  testWidgets('ba dáng linh vật khớp bản đã duyệt', (tester) async {
    await tester.binding.setSurfaceSize(const Size(320, 420));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: Scaffold(
          backgroundColor: BalanceColors.paperBlue,
          body: Column(
            children: [
              for (final shape in MascotShape.values)
                Expanded(child: WalkingMascot(shape: shape, animate: false)),
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(Column).first,
      matchesGoldenFile('goldens/mascot_shapes.png'),
    );
  });

  testWidgets('khung hình lúc quay đầu khớp bản đã duyệt', (tester) async {
    // Chốt riêng khoảnh khắc quay đầu: đây là chỗ nhiều thứ xảy ra cùng lúc
    // nhất — rời đất, co chân, bóp bề ngang — nên cũng dễ vỡ nhất khi có ai
    // chỉnh lại một con số trong bảng tư thế.
    await tester.binding.setSurfaceSize(const Size(360, 180));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: Scaffold(
          backgroundColor: BalanceColors.paperBlue,
          body: Row(
            children: [
              for (var i = 0; i < 3; i++)
                SizedBox(
                  width: 120,
                  height: 180,
                  child: CustomPaint(
                    painter: MascotPainter(
                      pose: mascotPoseAt(0.42 + 0.025 * i),
                      shape: MascotShape.fit,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(Row).first,
      matchesGoldenFile('goldens/mascot_turn.png'),
    );
  });

  testWidgets('linh vật vẽ bằng nét, không còn dán ảnh', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: WalkingMascot(shape: MascotShape.fit, animate: false),
        ),
      ),
    );

    // Không còn tấm ảnh nào. Đây mới là điều kiện để chân tách rời khỏi thân
    // mà bước — chứ không phải chuyện gọn gàng về code.
    expect(find.byType(Image), findsNothing);
    expect(_painterIn(tester).shape, MascotShape.fit);
  });

  testWidgets('tắt animate thì đứng yên đúng khung hình đã chọn', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: WalkingMascot(shape: MascotShape.slim, animate: false),
        ),
      ),
    );

    expect(
      _painterIn(tester).pose.travel,
      mascotPoseAt(kMascotRestPhase).travel,
    );
  });

  testWidgets('bật animate thì thật sự nhích đi chứ không đứng hình', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: WalkingMascot(shape: MascotShape.fit)),
      ),
    );

    final start = _painterIn(tester).pose;
    await tester.pump(const Duration(seconds: 2));
    final later = _painterIn(tester).pose;
    expect(later.travel, greaterThan(start.travel));

    // Đi vài vòng rồi phải nghỉ. Chạy mãi thì `pumpAndSettle` treo vĩnh viễn
    // và mọi test chạm tới trang chủ chết theo.
    await tester.pumpAndSettle();
    expect(find.byType(WalkingMascot), findsOneWidget);
  });
}
