import 'dart:async';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:balance/features/chat/data/chat_api.dart';
import 'package:balance/features/chat/presentation/chat_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../../helpers/fake_auth_gateway.dart';

class _FakeChatApi extends ChatApi {
  _FakeChatApi()
    : super(client: MockClient((_) async => http.Response('', 500)));

  int calls = 0;

  @override
  Stream<ChatEvent> streamChat({
    required String message,
    required List<ChatMessagePayload> history,
    required String accessToken,
    String timezone = 'Asia/Ho_Chi_Minh',
  }) async* {
    calls++;
    yield const ChatEvent(
      name: 'delta',
      data: {'text': 'Một tô phở bò có khoảng 480 kcal.'},
    );
    yield const ChatEvent(
      name: 'sources',
      data: {
        'items': [
          {'label': 'Phở bò', 'source': 'vnmeal'},
        ],
      },
    );
    yield const ChatEvent(name: 'done', data: {});
  }
}

class _DelayedRefreshGateway extends FakeAuthGateway {
  _DelayedRefreshGateway()
    : super(
        session: AuthSession(
          accessToken: 'expired-access-token',
          refreshToken: 'refresh-token',
          expiresIn: 0,
          expiresAt: DateTime.utc(2000),
          user: const AuthUser(
            id: 'user-id',
            email: 'an@example.com',
            displayName: 'An',
            role: 'user',
          ),
        ),
      );

  final refreshCompleter = Completer<AuthSession>();

  @override
  Future<AuthSession> refresh(String refreshToken) => refreshCompleter.future;
}

Future<AppState> _signedInState({AuthGateway? authGateway}) async {
  final state = await AppState.restore(
    MemoryAppStorage(),
    authGateway: authGateway ?? FakeAuthGateway(),
  );
  await state.signIn(email: 'an@example.com', password: 'matkhau123');
  return state;
}

void main() {
  testWidgets('hiện nguồn catalog bên dưới câu trả lời RAG', (tester) async {
    final state = await _signedInState();
    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: ChatScreen(api: _FakeChatApi()),
        ),
      ),
    );

    await tester.tap(find.text('Phở bò khác bún bò thế nào?'));
    await tester.pumpAndSettle();

    expect(find.text('Một tô phở bò có khoảng 480 kcal.'), findsOneWidget);
    expect(find.text('Nguồn: Phở bò (vnmeal)'), findsOneWidget);
  });

  testWidgets('dừng trước khi refresh token xong không khởi động stream cũ', (
    tester,
  ) async {
    final auth = _DelayedRefreshGateway();
    final api = _FakeChatApi();
    final state = await _signedInState(authGateway: auth);
    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: ChatScreen(api: api),
        ),
      ),
    );

    await tester.tap(find.text('Tuần này tôi nạp bao nhiêu calo?'));
    await tester.pump();
    await tester.tap(find.byTooltip('Dừng'));
    auth.refreshCompleter.complete(FakeAuthGateway().session);
    await tester.pumpAndSettle();

    expect(api.calls, 0);
  });
}
