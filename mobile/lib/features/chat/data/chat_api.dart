import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:http/http.dart' as http;

/// Một event SSE đã được giải mã JSON.
class ChatEvent {
  const ChatEvent({required this.name, required this.data});

  final String name;
  final Map<String, dynamic> data;
}

/// Parser chịu được cả ranh giới chunk nằm giữa UTF-8 hoặc giữa JSON.
///
/// `utf8.decoder` ở [ChatApi] lo phần byte → ký tự; lớp này chỉ giữ phần văn
/// bản chưa đủ `\n\n`, nên không bao giờ cố parse một nửa object JSON.
class ChatSseDecoder {
  String _buffer = '';

  List<ChatEvent> addText(String chunk) {
    _buffer += chunk.replaceAll('\r\n', '\n').replaceAll('\r', '\n');
    return _drain();
  }

  List<ChatEvent> finish() {
    if (_buffer.trim().isEmpty) return const [];
    final block = _buffer;
    _buffer = '';
    return _parseBlock(block);
  }

  List<ChatEvent> _drain() {
    final events = <ChatEvent>[];
    while (true) {
      final boundary = _buffer.indexOf('\n\n');
      if (boundary < 0) break;
      final block = _buffer.substring(0, boundary);
      _buffer = _buffer.substring(boundary + 2);
      events.addAll(_parseBlock(block));
    }
    return events;
  }

  List<ChatEvent> _parseBlock(String block) {
    String name = 'message';
    final dataLines = <String>[];
    for (final line in block.split('\n')) {
      if (line.startsWith('event:')) {
        name = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.add(line.substring(5).trimLeft());
      }
    }
    if (dataLines.isEmpty) return const [];
    try {
      final decoded = jsonDecode(dataLines.join('\n'));
      if (decoded is Map) {
        return [
          ChatEvent(name: name, data: Map<String, dynamic>.from(decoded)),
        ];
      }
    } on FormatException {
      // Một block hỏng không được làm chết cả stream; backend sẽ gửi error
      // event riêng khi có thể.
    }
    return const [];
  }
}

class ChatApiException implements Exception {
  const ChatApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

class ChatApi {
  ChatApi({
    http.Client? client,
    Uri? baseUrl,
    Duration? connectTimeout,
    Duration? idleTimeout,
  }) : _client = client ?? http.Client(),
       _ownsClient = client == null,
       _baseUrl = baseUrl ?? ApiConfig.baseUrl,
       _connectTimeout = connectTimeout ?? const Duration(seconds: 15),
       _idleTimeout = idleTimeout ?? const Duration(seconds: 95);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _connectTimeout;
  final Duration _idleTimeout;

  Stream<ChatEvent> streamChat({
    required String message,
    required List<ChatMessagePayload> history,
    required String accessToken,
    String timezone = 'Asia/Ho_Chi_Minh',
  }) async* {
    final trimmed = message.trim();
    if (trimmed.isEmpty) {
      throw const ChatApiException('Hãy nhập câu hỏi trước nhé.');
    }
    final request =
        http.Request('POST', _baseUrl.resolve('/api/v1/chat/stream'))
          ..headers.addAll({
            'content-type': 'application/json',
            'accept': 'text/event-stream',
            'authorization': 'Bearer $accessToken',
          })
          ..body = jsonEncode({
            'message': trimmed,
            'history': history.take(12).map((item) => item.toJson()).toList(),
            'timezone': timezone,
          });

    late http.StreamedResponse response;
    try {
      response = await _client.send(request).timeout(_connectTimeout);
    } on TimeoutException {
      throw const ChatApiException('Kết nối chatbot quá lâu. Hãy thử lại.');
    } on SocketException {
      throw const ChatApiException('Không kết nối được chatbot.');
    } on http.ClientException {
      throw const ChatApiException('Không kết nối được chatbot.');
    }
    if (response.statusCode != 200) {
      final body = await response.stream.bytesToString();
      throw ChatApiException(_extractError(body, response.statusCode));
    }

    final decoder = ChatSseDecoder();
    try {
      await for (final text
          in utf8.decoder.bind(response.stream).timeout(_idleTimeout)) {
        for (final event in decoder.addText(text)) {
          yield event;
        }
      }
      for (final event in decoder.finish()) {
        yield event;
      }
    } on TimeoutException {
      throw const ChatApiException('Chatbot phản hồi quá lâu. Hãy thử lại.');
    } on SocketException {
      throw const ChatApiException('Kết nối chatbot bị gián đoạn.');
    } on http.ClientException {
      throw const ChatApiException('Kết nối chatbot bị gián đoạn.');
    }
  }

  String _extractError(String body, int statusCode) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } on Object {
      // Dùng thông báo theo status nếu body không phải JSON.
    }
    return 'Chatbot chưa sẵn sàng (HTTP $statusCode).';
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class ChatMessagePayload {
  const ChatMessagePayload({required this.role, required this.content});

  final String role;
  final String content;

  Map<String, String> toJson() => {'role': role, 'content': content};
}
