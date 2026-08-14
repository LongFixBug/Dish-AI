import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:http/http.dart' as http;

/// Cổng đồng bộ nhật ký lên MealLog của backend.
abstract interface class MealGateway {
  Future<void> upsert(
    JournalEntry entry, {
    required String accessToken,
    required String source,
    String? analyzeSource,
  });
}

/// Ghi một bữa ăn theo client_entry_id để bấm lưu lại không tạo bản ghi đôi.
class MealApi implements MealGateway {
  MealApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 20);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  @override
  Future<void> upsert(
    JournalEntry entry, {
    required String accessToken,
    required String source,
    String? analyzeSource,
  }) async {
    final response = await _request('/api/v1/meals', {
      'client_entry_id': entry.id,
      'eaten_at': entry.loggedAt.toUtc().toIso8601String(),
      'meal_type': entry.mealType.name,
      'dish_name': entry.dishName,
      'total_grams': entry.totalGrams,
      'calories': entry.calories,
      'protein_g': entry.proteinGrams,
      'fat_g': entry.fatGrams,
      'carbs_g': entry.carbsGrams,
      'fiber_g': entry.fiberGrams,
      'source': source,
      'analyze_source': ?analyzeSource,
    }, accessToken: accessToken);
    if (response.statusCode != 200 && response.statusCode != 201) {
      throw MealApiException(
        _extractError(response.bodyBytes, response.statusCode),
      );
    }
  }

  Future<http.Response> _request(
    String path,
    Map<String, dynamic> body, {
    required String accessToken,
  }) async {
    try {
      return await _client
          .post(
            _baseUrl.resolve(path),
            headers: {
              'content-type': 'application/json',
              'authorization': 'Bearer $accessToken',
            },
            body: jsonEncode(body),
          )
          .timeout(_timeout);
    } on TimeoutException {
      throw const MealApiException(
        'Đồng bộ nhật ký quá lâu. Bữa ăn trên máy vẫn được giữ lại.',
      );
    } on SocketException {
      throw const MealApiException(
        'Không kết nối được máy chủ nhật ký. Bữa ăn trên máy vẫn được giữ lại.',
      );
    } on http.ClientException {
      throw const MealApiException(
        'Không kết nối được máy chủ nhật ký. Bữa ăn trên máy vẫn được giữ lại.',
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
      // Fall through to the status-based message.
    }
    return 'Không thể đồng bộ nhật ký (HTTP $statusCode).';
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class MealApiException implements Exception {
  const MealApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
