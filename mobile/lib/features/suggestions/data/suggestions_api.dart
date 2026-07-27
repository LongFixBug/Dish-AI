import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:balance/features/suggestions/domain/suggested_dish.dart';
import 'package:http/http.dart' as http;

/// Lấy gợi ý món theo phần dinh dưỡng còn lại của hôm nay.
abstract interface class SuggestionsGateway {
  Future<SuggestionResult> fetch({
    required SuggestionQuery query,
    required String accessToken,
  });
}

/// Phần đã ăn hôm nay + ràng buộc của người dùng.
class SuggestionQuery {
  const SuggestionQuery({
    required this.consumedCalories,
    required this.consumedProtein,
    required this.consumedFat,
    required this.consumedCarbs,
    this.excludeDishNames = const [],
    this.allergies = const [],
    this.preferences = const [],
    this.limit = 4,
  });

  final double consumedCalories;
  final double consumedProtein;
  final double consumedFat;
  final double consumedCarbs;
  final List<String> excludeDishNames;
  final List<String> allergies;
  final List<String> preferences;
  final int limit;

  Map<String, dynamic> toJson() => {
    'consumed_calories': consumedCalories,
    'consumed_protein_g': consumedProtein,
    'consumed_fat_g': consumedFat,
    'consumed_carbs_g': consumedCarbs,
    'exclude_dish_names': excludeDishNames,
    'allergies': allergies,
    'preferences': preferences,
    'limit': limit,
  };
}

class SuggestionsApi implements SuggestionsGateway {
  SuggestionsApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 20);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  @override
  Future<SuggestionResult> fetch({
    required SuggestionQuery query,
    required String accessToken,
  }) async {
    try {
      final response = await _client
          .post(
            _baseUrl.resolve('/api/v1/suggestions'),
            headers: {
              'content-type': 'application/json',
              'authorization': 'Bearer $accessToken',
            },
            body: jsonEncode(query.toJson()),
          )
          .timeout(_timeout);
      if (response.statusCode != 200) {
        throw SuggestionsApiException(
          _extractError(response.bodyBytes, response.statusCode),
        );
      }
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      if (decoded is! Map<String, dynamic>) {
        throw const SuggestionsApiException('Máy chủ trả về dữ liệu lạ.');
      }
      return SuggestionResult.fromJson(decoded);
    } on TimeoutException {
      throw const SuggestionsApiException('Lấy gợi ý quá lâu. Hãy thử lại.');
    } on SocketException {
      throw const SuggestionsApiException('Không kết nối được máy chủ.');
    } on http.ClientException {
      throw const SuggestionsApiException('Không kết nối được máy chủ.');
    } on FormatException {
      throw const SuggestionsApiException('Máy chủ trả về dữ liệu lạ.');
    }
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
    return 'Chưa lấy được gợi ý (HTTP $statusCode).';
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class SuggestionsApiException implements Exception {
  const SuggestionsApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
