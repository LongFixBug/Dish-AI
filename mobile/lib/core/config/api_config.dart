import 'dart:io';

import 'package:flutter/foundation.dart';

abstract final class ApiConfig {
  static Uri get baseUrl {
    const configuredUrl = String.fromEnvironment('API_BASE_URL');
    if (configuredUrl.isNotEmpty) {
      final uri = Uri.parse(_withoutTrailingSlash(configuredUrl));
      if (!uri.hasAuthority || !const {'http', 'https'}.contains(uri.scheme)) {
        throw StateError('API_BASE_URL phải là URL HTTP(S) hợp lệ.');
      }
      if (kReleaseMode && uri.scheme != 'https') {
        throw StateError('Bản release bắt buộc dùng API_BASE_URL qua HTTPS.');
      }
      return uri;
    }

    if (kReleaseMode) {
      throw StateError('Bản release bắt buộc cấu hình API_BASE_URL.');
    }

    final host = Platform.isAndroid ? '10.0.2.2' : '127.0.0.1';
    return Uri.parse('http://$host:8000');
  }

  static String _withoutTrailingSlash(String value) {
    return value.endsWith('/') ? value.substring(0, value.length - 1) : value;
  }
}
