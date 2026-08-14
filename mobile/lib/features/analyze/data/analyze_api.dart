import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:balance/core/config/api_config.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:http/http.dart' as http;

class AnalyzeApi {
  AnalyzeApi({
    http.Client? client,
    Uri? baseUrl,
    Duration? timeout,
    String? accessToken,
    Future<String> Function()? accessTokenProvider,
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null,
       _baseUrl = baseUrl ?? ApiConfig.baseUrl,
       _timeout = timeout ?? const Duration(seconds: 90),
       _tokenSource = _TokenSource(accessToken, accessTokenProvider);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;
  final _TokenSource _tokenSource;

  Future<AnalyzeResult> analyzeImage({
    required Uint8List bytes,
    required String filename,
  }) async {
    _validateImage(bytes, filename);
    final accessToken = await _tokenSource.read();
    if (accessToken == null || accessToken.isEmpty) {
      throw const AnalyzeApiException('Phiên đăng nhập đã kết thúc.');
    }
    final request =
        http.MultipartRequest('POST', _baseUrl.resolve('/api/v1/analyze'))
          ..headers['authorization'] = 'Bearer $accessToken'
          ..files.add(
            http.MultipartFile.fromBytes(
              'file',
              bytes,
              filename: filename,
              contentType: _imageMediaType(filename, bytes),
            ),
          );

    try {
      final streamed = await _client.send(request).timeout(_timeout);
      final response = await http.Response.fromStream(streamed);
      Map<String, dynamic>? json;
      try {
        json = _decodeObject(response.bodyBytes);
      } on FormatException {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          throw AnalyzeApiException(
            'Backend tạm thời không phục vụ được yêu cầu '
            '(HTTP ${response.statusCode}).',
          );
        }
        rethrow;
      }

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw AnalyzeApiException(_extractError(json, response.statusCode));
      }

      final result = AnalyzeResult.fromJson(json);
      if (result.error case final String message when message.isNotEmpty) {
        throw AnalyzeApiException(message);
      }
      return result;
    } on AnalyzeApiException {
      rethrow;
    } on TimeoutException {
      throw const AnalyzeApiException(
        'Phân tích hơi lâu. Hãy kiểm tra backend rồi thử lại.',
      );
    } on http.ClientException catch (_) {
      throw AnalyzeApiException(
        'Không kết nối được backend tại $_baseUrl. '
        'Hãy kiểm tra API đang chạy và địa chỉ API_BASE_URL.',
      );
    } on SocketException catch (_) {
      throw AnalyzeApiException(
        'Không kết nối được backend tại $_baseUrl. '
        'Hãy kiểm tra API đang chạy và địa chỉ API_BASE_URL.',
      );
    } on FormatException {
      throw const AnalyzeApiException(
        'Backend trả về dữ liệu không đúng định dạng.',
      );
    }
  }

  Future<AnalyzeResult> analyzeText({
    required String foodName,
    double grams = 100.0,
  }) async {
    final normalizedName = foodName.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (normalizedName.isEmpty || normalizedName.length > 300) {
      throw const AnalyzeApiException('Tên món phải có từ 1 đến 300 ký tự.');
    }
    if (!grams.isFinite || grams <= 0 || grams > 10000) {
      throw const AnalyzeApiException('Khối lượng phải từ 1 đến 10.000 gram.');
    }
    final accessToken = await _tokenSource.read();
    if (accessToken == null || accessToken.isEmpty) {
      throw const AnalyzeApiException('Phiên đăng nhập đã kết thúc.');
    }

    try {
      final response = await _client
          .post(
            _baseUrl.resolve('/api/v1/analyze/text'),
            headers: {
              'content-type': 'application/json',
              'authorization': 'Bearer $accessToken',
            },
            body: jsonEncode({'food_name': normalizedName, 'grams': grams}),
          )
          .timeout(_timeout);
      Map<String, dynamic>? json;
      try {
        json = _decodeObject(response.bodyBytes);
      } on FormatException {
        if (response.statusCode < 200 || response.statusCode >= 300) {
          throw AnalyzeApiException(
            'Backend tạm thời không phục vụ được yêu cầu '
            '(HTTP ${response.statusCode}).',
          );
        }
        rethrow;
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw AnalyzeApiException(_extractError(json, response.statusCode));
      }
      final result = AnalyzeResult.fromJson(json);
      if (result.error case final String message when message.isNotEmpty) {
        throw AnalyzeApiException(message);
      }
      return result;
    } on AnalyzeApiException {
      rethrow;
    } on TimeoutException {
      throw const AnalyzeApiException(
        'Phân tích hơi lâu. Hãy kiểm tra backend rồi thử lại.',
      );
    } on http.ClientException {
      throw AnalyzeApiException(
        'Không kết nối được backend tại $_baseUrl. '
        'Hãy kiểm tra API đang chạy và địa chỉ API_BASE_URL.',
      );
    } on SocketException {
      throw AnalyzeApiException(
        'Không kết nối được backend tại $_baseUrl. '
        'Hãy kiểm tra API đang chạy và địa chỉ API_BASE_URL.',
      );
    } on FormatException {
      throw const AnalyzeApiException(
        'Backend trả về dữ liệu không đúng định dạng.',
      );
    }
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class _TokenSource {
  const _TokenSource(this.value, this.provider);

  final String? value;
  final Future<String> Function()? provider;

  Future<String?> read() async => value ?? await provider?.call();
}

const _maxUploadBytes = 10 * 1024 * 1024;

void _validateImage(Uint8List bytes, String filename) {
  if (bytes.isEmpty) {
    throw const AnalyzeApiException('Ảnh đang trống. Hãy chọn ảnh khác.');
  }
  if (bytes.length > _maxUploadBytes) {
    throw const AnalyzeApiException('Ảnh vượt quá giới hạn 10 MB.');
  }
  final extension = filename.toLowerCase().split('.').last;
  if (extension == 'heic' || extension == 'heif') {
    throw const AnalyzeApiException(
      'Ảnh HEIC chưa được hỗ trợ. Hãy chọn ảnh JPEG, PNG hoặc WebP.',
    );
  }
}

class AnalyzeApiException implements Exception {
  const AnalyzeApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

Map<String, dynamic> _decodeObject(Uint8List bytes) {
  final decoded = jsonDecode(utf8.decode(bytes));
  if (decoded is! Map<String, dynamic>) {
    throw const FormatException('Expected a JSON object');
  }
  return decoded;
}

String _extractError(Map<String, dynamic> json, int statusCode) {
  final detail = json['detail'];
  if (detail is String && detail.isNotEmpty) return detail;
  if (detail is Map) {
    final message = detail['message'];
    if (message is String && message.isNotEmpty) return message;
  }
  if (detail is List && detail.isNotEmpty) {
    final first = detail.first;
    if (first is Map && first['msg'] is String) return first['msg'] as String;
  }
  return 'Backend từ chối ảnh (HTTP $statusCode).';
}

http.MediaType _imageMediaType(String filename, Uint8List bytes) {
  final extension = filename.toLowerCase().split('.').last;
  return switch (extension) {
    'png' => http.MediaType('image', 'png'),
    'webp' => http.MediaType('image', 'webp'),
    _ when bytes.length > 3 && bytes[0] == 0x89 && bytes[1] == 0x50 =>
      http.MediaType('image', 'png'),
    _ => http.MediaType('image', 'jpeg'),
  };
}
