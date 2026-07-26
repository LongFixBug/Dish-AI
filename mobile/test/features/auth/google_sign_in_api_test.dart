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
}
