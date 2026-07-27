import 'package:balance/features/auth/data/google_sign_in_api.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('fails clearly when the server client ID is not configured', () async {
    final gateway = GoogleSignInGateway(serverClientId: '');

    await expectLater(
      gateway.authenticate,
      throwsA(
        isA<GoogleSignInApiException>().having(
          (error) => error.message,
          'message',
          contains('GOOGLE_WEB_CLIENT_ID'),
        ),
      ),
    );
  });

  group('RetryableOnce', () {
    test('chạy lại sau mỗi lần hỏng', () async {
      // Nếu nhớ luôn Future lỗi, lần thử thứ hai chỉ await lại cái đã reject
      // và calls đứng ở 1 — người dùng bấm "thử lại" bao nhiêu cũng vô ích.
      final once = RetryableOnce();
      var calls = 0;
      Future<void> failing() async {
        calls += 1;
        throw StateError('init failed');
      }

      await expectLater(() => once.run(failing), throwsStateError);
      await expectLater(() => once.run(failing), throwsStateError);

      expect(calls, 2);
    });

    test('chỉ chạy một lần khi đã thành công', () async {
      final once = RetryableOnce();
      var calls = 0;
      Future<void> succeeding() async => calls += 1;

      await once.run(succeeding);
      await once.run(succeeding);

      expect(calls, 1);
    });

    test('hỏng rồi thành công thì thôi không chạy lại nữa', () async {
      final once = RetryableOnce();
      var calls = 0;
      var shouldFail = true;
      Future<void> task() async {
        calls += 1;
        if (shouldFail) throw StateError('init failed');
      }

      await expectLater(() => once.run(task), throwsStateError);
      shouldFail = false;
      await once.run(task);
      await once.run(task);

      expect(calls, 2);
    });
  });
}
