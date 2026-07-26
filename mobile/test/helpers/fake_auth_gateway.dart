import 'package:balance/features/auth/data/auth_api.dart';

class FakeAuthGateway implements AuthGateway {
  FakeAuthGateway({AuthSession? session})
    : session =
          session ??
          AuthSession(
            accessToken: 'access-token',
            refreshToken: 'refresh-token',
            expiresIn: 900,
            user: const AuthUser(
              id: 'user-id',
              email: 'an@example.com',
              displayName: 'Nguyễn Văn An',
              role: 'user',
            ),
          );

  final AuthSession session;
  String? loginEmail;
  String? loginPassword;
  String? googleIdToken;
  String? registerName;
  bool loggedOut = false;

  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async {
    loginEmail = email;
    loginPassword = password;
    return session;
  }

  @override
  Future<AuthSession> register({
    required String email,
    required String password,
    required String displayName,
  }) async {
    loginEmail = email;
    loginPassword = password;
    registerName = displayName;
    return session;
  }

  @override
  Future<AuthSession> refresh(String refreshToken) async => session;

  @override
  Future<AuthSession> loginWithGoogle({required String idToken}) async {
    googleIdToken = idToken;
    return session;
  }

  @override
  Future<void> logout({
    required String accessToken,
    required String refreshToken,
  }) async {
    loggedOut = true;
  }
}
