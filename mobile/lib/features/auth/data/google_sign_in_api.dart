import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter/foundation.dart';

abstract interface class GoogleIdentityGateway {
  Future<String> authenticate();

  Future<void> signOut();
}

class GoogleSignInGateway implements GoogleIdentityGateway {
  GoogleSignInGateway({
    GoogleSignIn? signIn,
    String? serverClientId,
    String? clientId,
  }) : _signIn = signIn ?? GoogleSignIn.instance,
       _serverClientId =
           serverClientId ??
           const String.fromEnvironment('GOOGLE_WEB_CLIENT_ID'),
       _clientId = clientId ?? const String.fromEnvironment('IOS_CLIENT_ID');

  final GoogleSignIn _signIn;
  final String _serverClientId;
  final String _clientId;
  final RetryableOnce _initialization = RetryableOnce();

  @override
  Future<String> authenticate() async {
    if (_serverClientId.isEmpty) {
      throw const GoogleSignInApiException(
        'Thiếu GOOGLE_WEB_CLIENT_ID khi build ứng dụng.',
      );
    }
    try {
      await _initialization.run(
        () => _signIn.initialize(
          clientId: kIsWeb
              ? _serverClientId
              : (_clientId.isEmpty ? null : _clientId),
          serverClientId: _serverClientId,
        ),
      );
      final account = await _signIn.authenticate();
      final idToken = account.authentication.idToken;
      if (idToken == null || idToken.isEmpty) {
        throw const GoogleSignInApiException(
          'Google không trả về ID token để xác thực máy chủ.',
        );
      }
      return idToken;
    } on GoogleSignInApiException {
      rethrow;
    } on GoogleSignInException catch (error) {
      throw GoogleSignInApiException(switch (error.code) {
        GoogleSignInExceptionCode.canceled => 'Bạn đã hủy đăng nhập Google.',
        GoogleSignInExceptionCode.clientConfigurationError ||
        GoogleSignInExceptionCode.providerConfigurationError =>
          'Cấu hình Google Sign-In chưa đúng cho bản ứng dụng này.',
        GoogleSignInExceptionCode.uiUnavailable =>
          'Không thể mở màn hình đăng nhập Google.',
        _ => 'Không thể đăng nhập Google. Hãy thử lại.',
      });
    }
  }

  @override
  Future<void> signOut() => _signIn.signOut();
}

/// Chạy một tác vụ đúng một lần, nhưng chỉ ghi nhớ kết quả THÀNH CÔNG.
///
/// Kiểu `_pending ??= task()` thông thường nhớ luôn cả Future lỗi: một lần
/// initialize hỏng vì mất mạng sẽ khiến mọi lần gọi sau đó `await` lại đúng
/// Future đã reject đó, và nút "thử lại" thành vô nghĩa cho tới khi tắt app.
class RetryableOnce {
  Future<void>? _pending;

  Future<void> run(Future<void> Function() task) {
    return _pending ??= task().onError<Object>((error, stackTrace) {
      _pending = null;
      Error.throwWithStackTrace(error, stackTrace);
    });
  }
}

class GoogleSignInApiException implements Exception {
  const GoogleSignInApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
