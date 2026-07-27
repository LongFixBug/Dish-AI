import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:balance/core/config/api_config.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

/// Tách món chính khỏi nền thành sticker PNG viền trắng.
abstract interface class StickerGateway {
  Future<Uint8List?> cutOut({
    required Uint8List imageBytes,
    required String filename,
    required String accessToken,
  });
}

class StickerApi implements StickerGateway {
  StickerApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 45);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  /// Trả sticker, hoặc ``null`` khi không tạo được.
  ///
  /// Sticker chỉ là phần nhìn cho vui: mọi trục trặc đều nuốt về ``null`` để
  /// màn hình kết quả rơi về ảnh gốc, chứ không được làm hỏng cả lượt phân tích.
  @override
  Future<Uint8List?> cutOut({
    required Uint8List imageBytes,
    required String filename,
    required String accessToken,
  }) async {
    final request =
        http.MultipartRequest('POST', _baseUrl.resolve('/api/v1/sticker'))
          ..headers['authorization'] = 'Bearer $accessToken'
          ..files.add(
            http.MultipartFile.fromBytes(
              'file',
              imageBytes,
              filename: filename,
              contentType: _mediaType(filename),
            ),
          );
    try {
      final streamed = await _client.send(request).timeout(_timeout);
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode != 200 || response.bodyBytes.isEmpty) return null;
      return response.bodyBytes;
    } on TimeoutException {
      return null;
    } on SocketException {
      return null;
    } on http.ClientException {
      return null;
    }
  }

  MediaType _mediaType(String filename) {
    final lower = filename.toLowerCase();
    if (lower.endsWith('.png')) return MediaType('image', 'png');
    if (lower.endsWith('.webp')) return MediaType('image', 'webp');
    return MediaType('image', 'jpeg');
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}
