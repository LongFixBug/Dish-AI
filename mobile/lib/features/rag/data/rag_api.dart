import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:http/http.dart' as http;

/// Cổng gọi RAG để màn hình có thể đổi sang fake gateway khi test.
abstract interface class RagGateway {
  Future<RagAnswer> ask({
    required String question,
    required String accessToken,
  });
}

class RagAnswer {
  const RagAnswer({required this.answer, required this.sources});

  factory RagAnswer.fromJson(Map<String, dynamic> json) {
    final answer = json['answer'];
    final rawSources = json['sources'];
    if (answer is! String || rawSources is! List) {
      throw const FormatException(
        'Thiếu answer hoặc sources trong phản hồi RAG.',
      );
    }
    return RagAnswer(
      answer: answer,
      sources: rawSources
          .whereType<Map>()
          .map((item) => RagSource.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
    );
  }

  final String answer;
  final List<RagSource> sources;
}

class RagSource {
  const RagSource({
    required this.documentId,
    required this.title,
    required this.source,
    required this.score,
  });

  factory RagSource.fromJson(Map<String, dynamic> json) {
    final documentId = json['document_id'];
    final title = json['title'];
    final source = json['source'];
    final score = json['score'];
    if (documentId is! String ||
        title is! String ||
        source is! String ||
        score is! num) {
      throw const FormatException('Nguồn RAG không đúng định dạng.');
    }
    return RagSource(
      documentId: documentId,
      title: title,
      source: source,
      score: score.toDouble(),
    );
  }

  final String documentId;
  final String title;
  final String source;
  final double score;
}

class RagApi implements RagGateway {
  RagApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 40);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  @override
  Future<RagAnswer> ask({
    required String question,
    required String accessToken,
  }) async {
    final normalizedQuestion = question.trim();
    if (normalizedQuestion.isEmpty) {
      throw const RagApiException('Hãy nhập câu hỏi trước.');
    }

    try {
      final response = await _client
          .post(
            _baseUrl.resolve('/api/v1/rag/chat'),
            headers: {
              'content-type': 'application/json',
              'authorization': 'Bearer $accessToken',
            },
            body: jsonEncode({'question': normalizedQuestion}),
          )
          .timeout(_timeout);
      if (response.statusCode != 200) {
        throw RagApiException(
          _extractError(response.bodyBytes, response.statusCode),
        );
      }

      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Phản hồi RAG không phải JSON object.');
      }
      return RagAnswer.fromJson(decoded);
    } on TimeoutException {
      throw const RagApiException('RAG trả lời quá lâu. Hãy thử lại.');
    } on SocketException {
      throw const RagApiException('Không kết nối được máy chủ FoodAI.');
    } on http.ClientException {
      throw const RagApiException('Không kết nối được máy chủ FoodAI.');
    } on FormatException {
      throw const RagApiException(
        'Máy chủ trả về dữ liệu RAG không đúng định dạng.',
      );
    }
  }

  String _extractError(List<int> bytes, int statusCode) {
    try {
      final decoded = jsonDecode(utf8.decode(bytes));
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } on Object {
      // Không phải JSON thì dùng thông báo có mã HTTP phía dưới.
    }
    return 'Chưa thể hỏi FoodAI (HTTP $statusCode).';
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class RagApiException implements Exception {
  const RagApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
