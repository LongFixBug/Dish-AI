import 'dart:convert';
import 'dart:typed_data';

import 'package:balance/features/analyze/presentation/scan_beam.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('running scan reveals the food with a depth effect', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 320,
          height: 480,
          child: ScanBeam(imageBytes: _pixel, running: true),
        ),
      ),
    );

    expect(find.bySemanticsLabel('Đang quét chiều sâu món ăn'), findsOneWidget);
    expect(find.byKey(const ValueKey('scan-3d-reveal')), findsOneWidget);
  });

  testWidgets('scan is flat before food then curves across the food zone', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 320,
          height: 480,
          child: ScanDepthFrame(imageBytes: _pixel, progress: 0.16),
        ),
      ),
    );
    expect(find.byKey(const ValueKey('scan-flat-beam')), findsOneWidget);
    expect(find.byKey(const ValueKey('scan-3d-arc')), findsNothing);

    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 320,
          height: 480,
          child: ScanDepthFrame(imageBytes: _pixel, progress: 0.56),
        ),
      ),
    );
    expect(find.byKey(const ValueKey('scan-flat-beam')), findsNothing);
    expect(find.byKey(const ValueKey('scan-3d-arc')), findsOneWidget);
  });

  testWidgets('curved scan never zooms or crops the selected photo', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 320,
          height: 480,
          child: ScanDepthFrame(
            imageBytes: _pixel,
            progress: 0.56,
            fit: BoxFit.contain,
          ),
        ),
      ),
    );

    expect(find.byType(Transform), findsNothing);
  });

  testWidgets('stopped scan shows the original photo without depth overlays', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: SizedBox(
          width: 320,
          height: 480,
          child: ScanBeam(imageBytes: _pixel, running: false),
        ),
      ),
    );

    expect(find.bySemanticsLabel('Đang quét chiều sâu món ăn'), findsNothing);
    expect(find.byKey(const ValueKey('scan-3d-reveal')), findsNothing);
    expect(find.byType(Image), findsOneWidget);
  });
}

final Uint8List _pixel = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ'
  'AAAADUlEQVQIHWP4z8DwHwAFgAI/ScL2WQAAAABJRU5ErkJggg==',
);
