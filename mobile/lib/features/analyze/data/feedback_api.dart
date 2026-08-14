import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:balance/core/config/api_config.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

/// Gửi ảnh kèm tên món đúng để đội ngũ cải thiện mô hình nhận diện.
abstract interface class FeedbackGateway {
  Future<void> submitCorrection({
    required Uint8List imageBytes,
    required String filename,
    required String correctDishName,
    required bool consentToTraining,
    required String accessToken,
    String? recognitionEventId,
    String captureSource = 'upload',
  });
}

class FeedbackApi implements FeedbackGateway {
  FeedbackApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 30);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  @override
  Future<void> submitCorrection({
    required Uint8List imageBytes,
    required String filename,
    required String correctDishName,
    required bool consentToTraining,
    required String accessToken,
    String? recognitionEventId,
    String captureSource = 'upload',
  }) async {
    final name = correctDishName.trim();
    if (name.isEmpty) {
      throw const FeedbackApiException('Hãy cho biết tên món đúng.');
    }
    // Ảnh của người dùng chỉ rời máy khi họ đồng ý — chặn ngay tại client
    // thay vì tin vào việc màn hình đã hỏi.
    if (!consentToTraining) {
      throw const FeedbackApiException(
        'Cần bạn đồng ý thì ảnh mới được gửi đi.',
      );
    }

    final request =
        http.MultipartRequest(
            'POST',
            _baseUrl.resolve('/api/v1/feedback/training-data'),
          )
          ..headers['authorization'] = 'Bearer $accessToken'
          ..fields['correct_dish_name'] = name
          ..fields['consent_to_training'] = 'true'
          ..fields['capture_source'] = captureSource
          ..files.add(
            http.MultipartFile.fromBytes(
              'file',
              imageBytes,
              filename: filename,
              contentType: _mediaType(filename),
            ),
          );
    if (recognitionEventId != null && recognitionEventId.isNotEmpty) {
      request.fields['recognition_event_id'] = recognitionEventId;
    }

    try {
      final streamed = await _client.send(request).timeout(_timeout);
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw FeedbackApiException(
          _extractError(response.bodyBytes, response.statusCode),
        );
      }
    } on TimeoutException {
      throw const FeedbackApiException('Gửi góp ý quá lâu. Hãy thử lại sau.');
    } on SocketException {
      throw const FeedbackApiException('Không kết nối được máy chủ.');
    } on http.ClientException {
      throw const FeedbackApiException('Không kết nối được máy chủ.');
    }
  }

  MediaType _mediaType(String filename) {
    final lower = filename.toLowerCase();
    if (lower.endsWith('.png')) return MediaType('image', 'png');
    if (lower.endsWith('.webp')) return MediaType('image', 'webp');
    return MediaType('image', 'jpeg');
  }

  String _extractError(List<int> bytes, int statusCode) {
    try {
      final decoded = jsonDecode(utf8.decode(bytes));
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } on Object {
      // Rơi xuống thông báo theo mã trạng thái.
    }
    return 'Không gửi được góp ý (HTTP $statusCode).';
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class FeedbackApiException implements Exception {
  const FeedbackApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
