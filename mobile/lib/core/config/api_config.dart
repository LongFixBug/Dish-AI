import 'dart:io';

abstract final class ApiConfig {
  static Uri get baseUrl {
    const configuredUrl = String.fromEnvironment('API_BASE_URL');
    if (configuredUrl.isNotEmpty) {
      return Uri.parse(_withoutTrailingSlash(configuredUrl));
    }

    final host = Platform.isAndroid ? '10.0.2.2' : '127.0.0.1';
    return Uri.parse('http://$host:8000');
  }

  static String _withoutTrailingSlash(String value) {
    return value.endsWith('/') ? value.substring(0, value.length - 1) : value;
  }
}
