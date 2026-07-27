import 'dart:typed_data';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

/// Kho giả: kho thật đi hỏi thư mục tài liệu qua platform channel, thứ không
/// tồn tại trong test — để nguyên thì spinner tải lại quay mãi và
/// pumpAndSettle hết giờ.
class _FakeStickerStore implements StickerStore {
  int prepareCalls = 0;

  @override
  Future<void> prepare() async => prepareCalls += 1;

  @override
  Future<String?> save({
    required String entryId,
    required Uint8List bytes,
  }) async => null;

  @override
  Future<Uint8List?> read(String? name) async => null;

  @override
  Future<void> delete(String? name) async {}
}

Future<Widget> _app({StickerStore? stickers}) async {
  final state = await AppState.restore(
    MemoryAppStorage(),
    authGateway: FakeAuthGateway(),
    stickerStore: stickers,
  );
  return AppScope(
    notifier: state,
    child: MaterialApp(
      theme: BalanceTheme.light,
      home: JournalScreen(now: DateTime(2026, 7, 27, 9)),
    ),
  );
}

void main() {
  testWidgets('màn Nhật ký có thao tác kéo xuống tải lại', (tester) async {
    await tester.pumpWidget(await _app());

    expect(find.byType(RefreshIndicator), findsOneWidget);
  });

  testWidgets('kéo xuống chạy xong và có gọi tải lại', (tester) async {
    final stickers = _FakeStickerStore();
    await tester.pumpWidget(await _app(stickers: stickers));

    // Ngày trống nên danh sách ngắn hơn màn hình: nếu physics không phải
    // AlwaysScrollable thì cử chỉ này không kích hoạt được gì.
    await tester.fling(find.byType(ListView), const Offset(0, 320), 1200);
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(
      stickers.prepareCalls,
      greaterThan(0),
      reason: 'phải dò lại sticker',
    );
    expect(find.byType(JournalScreen), findsOneWidget);
    expect(find.byType(RefreshIndicator), findsOneWidget);
  });
}
