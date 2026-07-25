import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:http/http.dart' as http;

abstract interface class AuthGateway {
  Future<AuthSession> login({required String email, required String password});

  Future<AuthSession> register({
    required String email,
    required String password,
    required String displayName,
  });

  Future<AuthSession> refresh(String refreshToken);

  Future<void> logout({
    required String accessToken,
    required String refreshToken,
  });
}

class UnavailableAuthGateway implements AuthGateway {
  const UnavailableAuthGateway();

  Never _unavailable() =>
      throw const AuthApiException('Dịch vụ đăng nhập chưa được cấu hình.');

  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) => Future.error(_unavailable());

  @override
  Future<AuthSession> register({
    required String email,
    required String password,
    required String displayName,
  }) => Future.error(_unavailable());

  @override
  Future<AuthSession> refresh(String refreshToken) =>
      Future.error(_unavailable());

  @override
  Future<void> logout({
    required String accessToken,
    required String refreshToken,
  }) => Future.error(_unavailable());
}

class AuthApi implements AuthGateway {
  AuthApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 20);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) => _sessionRequest('/api/v1/auth/login', {
    'email': email.trim().toLowerCase(),
    'password': password,
  });

  @override
  Future<AuthSession> register({
    required String email,
    required String password,
    required String displayName,
  }) => _sessionRequest('/api/v1/auth/register', {
    'email': email.trim().toLowerCase(),
    'password': password,
    'display_name': displayName.trim(),
  });

  @override
  Future<AuthSession> refresh(String refreshToken) =>
      _sessionRequest('/api/v1/auth/refresh', {'refresh_token': refreshToken});

  @override
  Future<void> logout({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _request(
      '/api/v1/auth/logout',
      {'refresh_token': refreshToken},
      accessToken: accessToken,
      expectedStatuses: const {204},
    );
  }

  Future<AuthSession> _sessionRequest(
    String path,
    Map<String, String> body,
  ) async {
    final response = await _request(
      path,
      body,
      expectedStatuses: const {200, 201},
    );
    try {
      return AuthSession.fromJson(response);
    } on FormatException {
      throw const AuthApiException(
        'Backend trả về phiên đăng nhập không đúng định dạng.',
      );
    }
  }

  Future<Map<String, dynamic>> _request(
    String path,
    Map<String, String> body, {
    String? accessToken,
    required Set<int> expectedStatuses,
  }) async {
    try {
      final response = await _client
          .post(
            _baseUrl.resolve(path),
            headers: {
              'content-type': 'application/json',
              if (accessToken != null) 'authorization': 'Bearer $accessToken',
            },
            body: jsonEncode(body),
          )
          .timeout(_timeout);
      final json = _decodeObject(response.bodyBytes);
      if (!expectedStatuses.contains(response.statusCode)) {
        throw AuthApiException(_extractError(json, response.statusCode));
      }
      return json;
    } on AuthApiException {
      rethrow;
    } on TimeoutException {
      throw const AuthApiException('Đăng nhập quá lâu. Hãy thử lại.');
    } on SocketException {
      throw const AuthApiException('Không kết nối được máy chủ đăng nhập.');
    } on http.ClientException {
      throw const AuthApiException('Không kết nối được máy chủ đăng nhập.');
    } on FormatException {
      throw const AuthApiException(
        'Backend trả về dữ liệu không đúng định dạng.',
      );
    }
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class AuthSession {
  AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresIn,
    required this.user,
    DateTime? expiresAt,
  }) : expiresAt =
           expiresAt ??
           DateTime.now().toUtc().add(Duration(seconds: expiresIn));

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    final userJson = json['user'];
    if (userJson is! Map) throw const FormatException('Missing auth user');
    return AuthSession(
      accessToken: _requiredString(json, 'access_token'),
      refreshToken: _requiredString(json, 'refresh_token'),
      expiresIn: (json['expires_in'] as num?)?.toInt() ?? 0,
      user: AuthUser.fromJson(Map<String, dynamic>.from(userJson)),
    );
  }

  final String accessToken;
  final String refreshToken;
  final int expiresIn;
  final DateTime expiresAt;
  final AuthUser user;
}

class AuthUser {
  const AuthUser({
    required this.id,
    required this.email,
    required this.displayName,
    required this.role,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
    id: _requiredString(json, 'id'),
    email: _requiredString(json, 'email'),
    displayName: _requiredString(json, 'display_name'),
    role: _requiredString(json, 'role'),
  );

  final String id;
  final String email;
  final String displayName;
  final String role;
}

class AuthApiException implements Exception {
  const AuthApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

Map<String, dynamic> _decodeObject(List<int> bytes) {
  if (bytes.isEmpty) return <String, dynamic>{};
  final decoded = jsonDecode(utf8.decode(bytes));
  if (decoded is! Map<String, dynamic>) {
    throw const FormatException('Expected JSON object');
  }
  return decoded;
}

String _extractError(Map<String, dynamic> json, int statusCode) {
  final detail = json['detail'];
  if (detail is String && detail.isNotEmpty) return detail;
  return 'Máy chủ từ chối yêu cầu đăng nhập (HTTP $statusCode).';
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String || value.isEmpty) {
    throw FormatException('Missing $key');
  }
  return value;
}
