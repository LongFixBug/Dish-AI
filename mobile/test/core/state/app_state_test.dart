import 'dart:async';

import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/nutrition/data/nutrition_goal_api.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
  test('profile, session and journal survive an app restart', () async {
    final storage = MemoryAppStorage();
    final auth = FakeAuthGateway();
    final state = await AppState.restore(storage, authGateway: auth);
    final profile = UserProfile(
      name: 'An',
      email: 'an@example.com',
      age: 25,
      heightCm: 170,
      weightKg: 65,
      targetWeightKg: 60,
      gender: 'Nam',
      activity: 'Vừa phải',
      goal: 'Giảm cân',
    );
    final result = AnalyzeResult.fromJson({
      'dish_name': 'Cơm tấm',
      'source': 'vision',
      'nutrition': {
        'total_calories': 650,
        'total_protein_g': 32,
        'total_fat_g': 22,
        'total_carbs_g': 78,
        'total_fiber_g': 4,
        'total_grams': 370,
      },
      'dishes': <Object>[],
    });

    await state.signIn(email: profile.email, password: 'matkhau123');
    await state.completeProfile(profile);
    await state.addJournalEntry(
      JournalEntry.fromAnalysis(
        result: result,
        loggedAt: DateTime(2026, 7, 25, 12),
        mealType: MealType.lunch,
      ),
    );

    final restored = await AppState.restore(storage, authGateway: auth);
    expect(restored.isSignedIn, isTrue);
    expect(restored.profile, profile);
    expect(restored.journalEntries.single.dishName, 'Cơm tấm');
    expect(restored.todayCalories(DateTime(2026, 7, 25)), 650);
  });

  test(
    'sign out clears user-scoped data and closes the active session',
    () async {
      final storage = MemoryAppStorage();
      final auth = FakeAuthGateway();
      final state = await AppState.restore(storage, authGateway: auth);

      await state.signIn(email: 'an@example.com', password: 'matkhau123');
      await state.completeProfile(
        const UserProfile(
          name: 'An',
          email: 'an@example.com',
          age: 25,
          heightCm: 170,
          weightKg: 65,
          targetWeightKg: 60,
          gender: 'Nam',
          activity: 'Vừa phải',
          goal: 'Giảm cân',
        ),
      );
      await state.updatePreferences({'Ít carb'});
      await state.signOut();

      final restored = await AppState.restore(storage, authGateway: auth);
      expect(restored.isSignedIn, isFalse);
      expect(restored.accessToken, isNull);
      expect(restored.profile, isNull);
      expect(restored.accountEmail, isEmpty);
      expect(restored.journalEntries, isEmpty);
      expect(restored.preferences, AppState.defaultPreferences);
      expect(auth.loggedOut, isTrue);
    },
  );

  test(
    'sign in delegates password verification to the backend gateway',
    () async {
      final auth = FakeAuthGateway();
      final state = await AppState.restore(
        MemoryAppStorage(),
        authGateway: auth,
      );

      await state.signIn(email: 'AN@EXAMPLE.COM', password: 'matkhau123');

      expect(auth.loginEmail, 'an@example.com');
      expect(auth.loginPassword, 'matkhau123');
      expect(state.accessToken, 'access-token');
      expect(state.isSignedIn, isTrue);
    },
  );

  test('profile persists nutrition safety flags', () async {
    const profile = UserProfile(
      name: 'An',
      email: 'an@example.com',
      age: 25,
      heightCm: 170,
      weightKg: 65,
      targetWeightKg: 60,
      gender: 'Nam',
      activity: 'Vừa phải',
      goal: 'Giảm cân',
      allergies: ['hải sản'],
      medicalConditions: ['tăng huyết áp'],
    );

    final decoded = UserProfile.fromJson(profile.toJson());

    expect(decoded, profile);
    expect(decoded.allergies, ['hải sản']);
    expect(decoded.medicalConditions, ['tăng huyết áp']);
    expect(decoded.hasNutritionSafetyFlags, isTrue);
  });

  test(
    'syncs a signed-in profile goal without blocking local persistence',
    () async {
      final gateway = _FakeNutritionGoalGateway();
      final auth = FakeAuthGateway();
      final state = await AppState.restore(
        MemoryAppStorage(),
        authGateway: auth,
        nutritionGoalGateway: gateway,
      );
      const profile = UserProfile(
        name: 'An',
        email: 'an@example.com',
        age: 25,
        heightCm: 170,
        weightKg: 65,
        targetWeightKg: 60,
        gender: 'Nam',
        activity: 'Vừa phải',
        goal: 'Giảm cân',
      );

      await state.signIn(email: profile.email, password: 'matkhau123');
      await state.completeProfile(profile);

      expect(gateway.profile, profile);
      expect(gateway.accessToken, 'access-token');
      expect(state.profile, profile);
    },
  );

  test('concurrent API calls share one refresh request', () async {
    final auth = _DelayedRefreshGateway();
    final state = await AppState.restore(MemoryAppStorage(), authGateway: auth);
    await state.signIn(email: 'an@example.com', password: 'matkhau123');

    final first = state.validAccessToken();
    final second = state.validAccessToken();
    await Future<void>.delayed(Duration.zero);

    expect(auth.refreshCalls, 1);
    auth.completeRefresh();
    expect(await Future.wait([first, second]), [
      'fresh-access',
      'fresh-access',
    ]);
  });
}

class _DelayedRefreshGateway implements AuthGateway {
  final _refreshCompleter = Completer<AuthSession>();
  int refreshCalls = 0;

  @override
  Future<AuthSession> login({
    required String email,
    required String password,
  }) async => AuthSession(
    accessToken: 'expired-access',
    refreshToken: 'refresh-token',
    expiresIn: 0,
    expiresAt: DateTime.utc(2000),
    user: const AuthUser(
      id: 'user-id',
      email: 'an@example.com',
      displayName: 'An',
      role: 'user',
    ),
  );

  @override
  Future<AuthSession> refresh(String refreshToken) {
    refreshCalls += 1;
    return _refreshCompleter.future;
  }

  void completeRefresh() {
    _refreshCompleter.complete(
      AuthSession(
        accessToken: 'fresh-access',
        refreshToken: 'fresh-refresh',
        expiresIn: 900,
        user: const AuthUser(
          id: 'user-id',
          email: 'an@example.com',
          displayName: 'An',
          role: 'user',
        ),
      ),
    );
  }

  @override
  Future<AuthSession> register({
    required String email,
    required String password,
    required String displayName,
  }) => throw UnimplementedError();

  @override
  Future<void> logout({
    required String accessToken,
    required String refreshToken,
  }) async {}
}

class _FakeNutritionGoalGateway implements NutritionGoalGateway {
  UserProfile? profile;
  String? accessToken;

  @override
  Future<void> save(UserProfile profile, {required String accessToken}) async {
    this.profile = profile;
    this.accessToken = accessToken;
  }
}
