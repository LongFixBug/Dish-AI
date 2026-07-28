import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:balance/core/config/api_config.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:http/http.dart' as http;

abstract interface class NutritionGoalGateway {
  Future<void> save(UserProfile profile, {required String accessToken});
}

abstract interface class NutritionGoalDetailsGateway {
  Future<NutritionGoalDetails> preview(
    UserProfile profile, {
    required String accessToken,
  });
}

class NutritionGoalApi
    implements NutritionGoalGateway, NutritionGoalDetailsGateway {
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

  @override
  Future<NutritionGoalDetails> preview(
    UserProfile profile, {
    required String accessToken,
  }) async {
    final response = await _clientRequest(
      '/api/v1/nutrition-goals/preview',
      profile.toNutritionGoalPayload(),
      accessToken: accessToken,
    );
    if (response.statusCode != 200) {
      throw NutritionGoalApiException(
        _extractError(response.bodyBytes, response.statusCode),
      );
    }
    try {
      return NutritionGoalDetails.fromJson(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>,
      );
    } on Object {
      throw const NutritionGoalApiException(
        'Máy chủ trả về bảng nhu cầu dinh dưỡng không hợp lệ.',
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

class NutritionGoalDetails {
  const NutritionGoalDetails({
    required this.maintenanceCalories,
    required this.targetCalories,
    required this.profile,
    required this.dailyTargets,
    required this.safetyStatus,
    required this.warnings,
  });

  factory NutritionGoalDetails.fromJson(Map<String, dynamic> json) {
    final profileJson = json['profile'];
    return NutritionGoalDetails(
      maintenanceCalories: _number(json['maintenance_calories']).round(),
      targetCalories: _number(json['target_calories']).round(),
      profile: NutritionProfileDetails.fromJson(
        profileJson is Map
            ? Map<String, dynamic>.from(profileJson)
            : const <String, dynamic>{},
      ),
      dailyTargets: (json['daily_targets'] is List
          ? (json['daily_targets'] as List)
                .whereType<Map>()
                .map(
                  (row) => NutritionTargetRow.fromJson(
                    Map<String, dynamic>.from(row),
                  ),
                )
                .toList(growable: false)
          : const <NutritionTargetRow>[]),
      safetyStatus: json['safety_status'] as String? ?? 'normal',
      warnings: (json['warnings'] is List
          ? (json['warnings'] as List).whereType<String>().toList()
          : const <String>[]),
    );
  }

  final int maintenanceCalories;
  final int targetCalories;
  final NutritionProfileDetails profile;
  final List<NutritionTargetRow> dailyTargets;
  final String safetyStatus;
  final List<String> warnings;
}

class NutritionProfileDetails {
  const NutritionProfileDetails({
    required this.age,
    required this.sex,
    required this.heightCm,
    required this.weightKg,
    required this.bmi,
    required this.bmiCategory,
    required this.nutritionGroup,
  });

  factory NutritionProfileDetails.fromJson(Map<String, dynamic> json) {
    return NutritionProfileDetails(
      age: _number(json['age']).round(),
      sex: json['sex'] as String? ?? 'other',
      heightCm: _number(json['height_cm']),
      weightKg: _number(json['weight_kg']),
      bmi: _number(json['bmi']),
      bmiCategory: json['bmi_category'] as String? ?? 'normal',
      nutritionGroup: json['nutrition_group'] as String? ?? 'normal',
    );
  }

  final int age;
  final String sex;
  final double heightCm;
  final double weightKg;
  final double bmi;
  final String bmiCategory;
  final String nutritionGroup;
}

class NutritionTargetRow {
  const NutritionTargetRow({
    required this.code,
    required this.nameVi,
    required this.category,
    required this.unit,
    required this.displayValue,
    required this.source,
  });

  factory NutritionTargetRow.fromJson(Map<String, dynamic> json) {
    return NutritionTargetRow(
      code: json['code'] as String? ?? '',
      nameVi: json['name_vi'] as String? ?? '',
      category: json['category'] as String? ?? 'micronutrient',
      unit: json['unit'] as String? ?? '',
      displayValue: json['display_value'] as String? ?? '-',
      source: json['source'] as String? ?? '',
    );
  }

  final String code;
  final String nameVi;
  final String category;
  final String unit;
  final String displayValue;
  final String source;
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

double _number(Object? value) => value is num ? value.toDouble() : 0;
