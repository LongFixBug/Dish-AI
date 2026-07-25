import 'dart:convert';

import 'package:balance/features/auth/data/auth_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('login sends credentials and parses a secure session', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/api/v1/auth/login');
      expect(jsonDecode(request.body), {
        'email': 'an@example.com',
        'password': 'matkhau123',
      });
      return http.Response(
        jsonEncode({
          'access_token': 'access-token',
          'refresh_token': 'refresh-token',
          'token_type': 'bearer',
          'expires_in': 900,
          'user': {
            'id': 'user-id',
            'email': 'an@example.com',
            'display_name': 'Nguyễn Văn An',
            'role': 'user',
            'created_at': '2026-07-25T00:00:00Z',
          },
        }),
        200,
        headers: {'content-type': 'application/json'},
      );
    });
    final api = AuthApi(client: client, baseUrl: Uri.parse('http://api.test'));

    final session = await api.login(
      email: 'an@example.com',
      password: 'matkhau123',
    );

    expect(session.accessToken, 'access-token');
    expect(session.refreshToken, 'refresh-token');
    expect(session.user.displayName, 'Nguyễn Văn An');
    api.close();
  });

  test('login exposes the friendly backend error', () async {
    final api = AuthApi(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({'detail': 'Email hoặc mật khẩu không đúng.'}),
          401,
          headers: {'content-type': 'application/json'},
        ),
      ),
      baseUrl: Uri.parse('http://api.test'),
    );

    expect(
      () => api.login(email: 'an@example.com', password: 'wrong-password'),
      throwsA(
        isA<AuthApiException>().having(
          (error) => error.message,
          'message',
          'Email hoặc mật khẩu không đúng.',
        ),
      ),
    );
    api.close();
  });
}
