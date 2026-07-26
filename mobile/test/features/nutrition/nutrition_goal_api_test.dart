import 'dart:convert';

import 'package:balance/features/nutrition/data/nutrition_goal_api.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  const profile = UserProfile(
    name: 'An',
    email: 'an@example.com',
    age: 30,
    heightCm: 170,
    weightKg: 75,
    targetWeightKg: 68,
    targetDays: 90,
    gender: 'Nam',
    activity: 'Vừa phải',
    goal: 'Giảm cân',
    medicalConditions: ['Tăng huyết áp'],
  );

  test(
    'saves the profile as the authenticated nutrition goal payload',
    () async {
      final client = MockClient((request) async {
        expect(request.method, 'POST');
        expect(request.url.path, '/api/v1/nutrition-goals');
        expect(request.headers['authorization'], 'Bearer access-token');
        expect(jsonDecode(request.body), {
          'age': 30,
          'sex': 'male',
          'height_cm': 170,
          'weight_kg': 75,
          'activity_level': 'moderate',
          'goal': 'lose',
          'target_weight_kg': 68,
          'target_days': 90,
          'pregnancy_status': 'none',
          'medical_conditions': ['Tăng huyết áp'],
        });
        return http.Response('{}', 200);
      });
      final api = NutritionGoalApi(
        client: client,
        baseUrl: Uri.parse('http://api.test'),
      );

      await api.save(profile, accessToken: 'access-token');
      api.close();
    },
  );

  test('turns backend validation errors into a friendly exception', () async {
    final api = NutritionGoalApi(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode({'detail': 'target_weight_kg phai thap hon weight_kg.'}),
          422,
        ),
      ),
      baseUrl: Uri.parse('http://api.test'),
    );

    await expectLater(
      () => api.save(profile, accessToken: 'access-token'),
      throwsA(
        isA<NutritionGoalApiException>().having(
          (error) => error.message,
          'message',
          'target_weight_kg phai thap hon weight_kg.',
        ),
      ),
    );
    api.close();
  });
}
