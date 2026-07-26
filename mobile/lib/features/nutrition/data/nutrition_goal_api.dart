import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:http/http.dart' as http;

abstract interface class NutritionGoalGateway {
  Future<void> save(UserProfile profile, {required String accessToken});
}

class NutritionGoalApi implements NutritionGoalGateway {
  NutritionGoalApi({http.Client? client, Uri? baseUrl, Duration? timeout})
    : _client = client ?? http.Client(),
      _ownsClient = client == null,
      _baseUrl = baseUrl ?? ApiConfig.baseUrl,
      _timeout = timeout ?? const Duration(seconds: 20);

  final http.Client _client;
  final bool _ownsClient;
  final Uri _baseUrl;
  final Duration _timeout;

  @override
  Future<void> save(UserProfile profile, {required String accessToken}) async {
    final response = await _clientRequest(
      '/api/v1/nutrition-goals',
      profile.toNutritionGoalPayload(),
      accessToken: accessToken,
    );
    if (response.statusCode != 200) {
      throw NutritionGoalApiException(
        _extractError(response.bodyBytes, response.statusCode),
      );
    }
  }

  Future<http.Response> _clientRequest(
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
      throw const NutritionGoalApiException(
        'Lưu mục tiêu quá lâu. Dữ liệu trên máy vẫn được giữ lại.',
      );
    } on SocketException {
      throw const NutritionGoalApiException(
        'Không kết nối được máy chủ dinh dưỡng.',
      );
    } on http.ClientException {
      throw const NutritionGoalApiException(
        'Không kết nối được máy chủ dinh dưỡng.',
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
    return 'Không thể lưu mục tiêu dinh dưỡng (HTTP $statusCode).';
  }

  void close() {
    if (_ownsClient) _client.close();
  }
}

class NutritionGoalApiException implements Exception {
  const NutritionGoalApiException(this.message);

  final String message;

  @override
  String toString() => message;
}

extension NutritionGoalPayload on UserProfile {
  Map<String, dynamic> toNutritionGoalPayload() => {
    'age': age,
    'sex': switch (gender) {
      'Nam' => 'male',
      'Nữ' => 'female',
      _ => 'other',
    },
    'height_cm': heightCm,
    'weight_kg': weightKg,
    'activity_level': switch (activity) {
      'Ít vận động' => 'sedentary',
      'Nhẹ nhàng' => 'light',
      'Năng động' => 'very_active',
      _ => 'moderate',
    },
    'goal': switch (goal) {
      'Giảm cân' => 'lose',
      'Tăng cân' => 'gain',
      _ => 'maintain',
    },
    'target_weight_kg': targetWeightKg,
    'target_days': targetDays,
    'pregnancy_status': 'none',
    'medical_conditions': medicalConditions,
  };
}
