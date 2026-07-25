import 'package:balance/core/widgets/pressable_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('button sinks while pressed and fires once on release', (
    tester,
  ) async {
    var tapCount = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: PressableButton(
              label: 'Bắt đầu',
              onPressed: () => tapCount += 1,
            ),
          ),
        ),
      ),
    );

    final label = find.text('Bắt đầu');
    final surface = find.byType(AnimatedContainer);
    final restingTransform = tester
        .widget<AnimatedContainer>(surface)
        .transform;
    final gesture = await tester.startGesture(tester.getCenter(label));

    await tester.pump(const Duration(milliseconds: 120));
    final pressedTransform = tester
        .widget<AnimatedContainer>(surface)
        .transform;

    expect(restingTransform?.storage[13], 0);
    expect(pressedTransform?.storage[13], closeTo(6, 0.1));

    await gesture.up();
    await tester.pumpAndSettle();

    expect(tapCount, 1);
    expect(
      tester.widget<AnimatedContainer>(surface).transform?.storage[13],
      closeTo(0, 0.1),
    );
  });
}
