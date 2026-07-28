import 'dart:convert';

import 'package:balance/features/journal/data/meal_api.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  final entry = JournalEntry(
    id: 'entry-1',
    dishName: 'Phở bò',
    loggedAt: DateTime(2026, 7, 27, 12, 30),
    mealType: MealType.lunch,
    calories: 480,
    proteinGrams: 28,
    fatGrams: 14,
    carbsGrams: 60,
    fiberGrams: 4,
    totalGrams: 450,
  );

  test('upsert gửi snapshot dinh dưỡng và client id lên backend', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/api/v1/meals');
      expect(request.headers['authorization'], 'Bearer access-token');
      expect(jsonDecode(request.body), {
        'client_entry_id': 'entry-1',
        'eaten_at': '2026-07-27T05:30:00.000Z',
        'meal_type': 'lunch',
        'dish_name': 'Phở bò',
        'total_grams': 450.0,
        'calories': 480.0,
        'protein_g': 28.0,
        'fat_g': 14.0,
        'carbs_g': 60.0,
        'fiber_g': 4.0,
        'source': 'analyze',
      });
      return http.Response('{}', 201);
    });
    final api = MealApi(client: client, baseUrl: Uri.parse('http://api.test'));

    await api.upsert(entry, accessToken: 'access-token', source: 'analyze');
    api.close();
  });

  test('trả lỗi thân thiện khi backend từ chối snapshot', () async {
    final api = MealApi(
      client: MockClient(
        (_) async => http.Response.bytes(
          utf8.encode(jsonEncode({'detail': 'Phiên đăng nhập đã kết thúc.'})),
          401,
        ),
      ),
      baseUrl: Uri.parse('http://api.test'),
    );

    await expectLater(
      () => api.upsert(entry, accessToken: 'expired', source: 'analyze'),
      throwsA(
        isA<MealApiException>().having(
          (error) => error.message,
          'message',
          'Phiên đăng nhập đã kết thúc.',
        ),
      ),
    );
    api.close();
  });
}
