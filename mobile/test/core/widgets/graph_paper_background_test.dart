import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('blue ribbon painter asks Flutter to repaint when it moves', () {
    const before = BlueRibbonPainter(progress: 0);
    const after = BlueRibbonPainter(progress: 0.5);

    expect(after.shouldRepaint(before), isTrue);
  });

  test(
    'snake enters from outside, crosses an apple, then leaves the screen',
    () {
      const size = Size(400, 800);

      final route = BlueRibbonPainter.routePoints(size);
      final routeAgain = BlueRibbonPainter.routePoints(size);
      final apple = BlueRibbonPainter.applePosition(size);

      expect(route, hasLength(5));
      expect(route, equals(routeAgain));
      expect(_isOutside(size, route.first), isTrue);
      expect(_isOutside(size, route.last), isTrue);
      expect(apple.dx, inInclusiveRange(0, size.width));
      expect(apple.dy, inInclusiveRange(0, size.height));
    },
  );

  test('apple returns only after the snake has left', () {
    const size = Size(400, 800);
    final fruitProgress = BlueRibbonPainter.appleProgress(size);

    expect(BlueRibbonPainter.appleIsVisible(size, 0), isTrue);
    expect(
      BlueRibbonPainter.appleIsVisible(size, fruitProgress - 0.01),
      isTrue,
    );
    expect(
      BlueRibbonPainter.appleIsVisible(size, fruitProgress + 0.01),
      isFalse,
    );
    expect(BlueRibbonPainter.appleIsVisible(size, 0.96), isTrue);
  });

  test('snake uses a quick, smooth travel path', () {
    expect(BlueRibbonPainter.cycleDuration, const Duration(seconds: 11));

    const size = Size(400, 800);
    final start = BlueRibbonPainter.snakePosition(size, 0);
    final middle = BlueRibbonPainter.snakePosition(size, 0.5);
    final end = BlueRibbonPainter.snakePosition(size, 1);
    final beforeTurn = BlueRibbonPainter.snakePosition(size, 0.374);
    final atTurn = BlueRibbonPainter.snakePosition(size, 0.375);
    final afterTurn = BlueRibbonPainter.snakePosition(size, 0.376);

    final incoming = atTurn - beforeTurn;
    final outgoing = afterTurn - atTurn;
    expect(_isOutside(size, start), isTrue);
    expect(_isOutside(size, end), isTrue);
    expect(_isOutside(size, middle), isFalse);
    expect(incoming.distance, greaterThan(0));
    expect(outgoing.distance, greaterThan(0));
    expect(incoming.direction - outgoing.direction, lessThan(0.75));
  });

  testWidgets('background paints the animated line behind its child', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: BalanceTheme.light,
        home: GraphPaperBackground(
          child: const Center(child: Text('Nội dung trên line')),
        ),
      ),
    );

    final painter = tester
        .widget<CustomPaint>(
          find.byWidgetPredicate(
            (widget) =>
                widget is CustomPaint && widget.painter is BlueRibbonPainter,
          ),
        )
        .painter;
    expect(painter, isA<BlueRibbonPainter>());
    expect(find.text('Nội dung trên line'), findsOneWidget);
  });

  testWidgets('static screens show a deterministic ribbon preview', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: GraphPaperBackground(child: SizedBox.expand()),
      ),
    );

    final painter = _backgroundPainter(tester);
    expect(painter.progress, BlueRibbonPainter.staticPreviewProgress);
    expect(painter.motionSeed, BlueRibbonPainter.fixedTestSeed);
  });

  testWidgets('snake line advances while the app motion scope is enabled', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: BalanceMotionScope(
          enabled: true,
          child: GraphPaperBackground(child: SizedBox.expand()),
        ),
      ),
    );
    await tester.pump();
    final before = _backgroundPainter(tester).progress;

    await tester.pump(const Duration(seconds: 1));

    expect(_backgroundPainter(tester).progress, greaterThan(before));
    expect(
      _backgroundPainter(tester).progress,
      closeTo(1 / BlueRibbonPainter.cycleDuration.inSeconds, 0.01),
    );
  });
}

bool _isOutside(Size size, Offset point) {
  return point.dx < 0 ||
      point.dx > size.width ||
      point.dy < 0 ||
      point.dy > size.height;
}

BlueRibbonPainter _backgroundPainter(WidgetTester tester) {
  return tester
          .widget<CustomPaint>(
            find.byWidgetPredicate(
              (widget) =>
                  widget is CustomPaint && widget.painter is BlueRibbonPainter,
            ),
          )
          .painter!
      as BlueRibbonPainter;
}
