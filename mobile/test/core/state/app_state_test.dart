import 'dart:async';
import 'dart:typed_data';

import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:balance/features/auth/data/google_sign_in_api.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
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

  test('revokes the refresh token even when Google sign-out fails', () async {
    // google_sign_in v7 bắt buộc initialize() trước; tài khoản đăng nhập bằng
    // mật khẩu chưa từng initialize nên signOut() ném. Nếu hai việc dùng chung
    // một try, refresh token sẽ sống tiếp 30 ngày trên máy chủ.
    final auth = FakeAuthGateway();
    final google = _FakeGoogleIdentityGateway(signOutThrows: true);
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: auth,
      googleIdentityGateway: google,
    );
    await state.signIn(email: 'an@example.com', password: 'mat-khau-123');

    await state.signOut();

    expect(auth.loggedOut, isTrue);
    expect(state.isSignedIn, isFalse);
  });

  test('signs in with a Google ID token through the auth gateway', () async {
    final auth = FakeAuthGateway();
    final google = _FakeGoogleIdentityGateway();
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: auth,
      googleIdentityGateway: google,
    );

    await state.signInWithGoogle();

    expect(auth.googleIdToken, 'google-id-token');
    expect(google.signInCalls, 1);
    expect(state.isSignedIn, isTrue);
    expect(state.accessToken, 'access-token');
  });

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

  test('sticker được ghi ra file và dọn sạch khi xoá bữa ăn', () async {
    // Ảnh nằm ngoài JSON: nhật ký chỉ giữ đường dẫn, nên xoá bữa ăn phải kéo
    // theo cả file, không thì thư mục tài liệu phình dần bằng ảnh mồ côi.
    final store = _RecordingStickerStore();
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
      stickerStore: store,
    );
    final entry = JournalEntry(
      id: 'entry-1',
      dishName: 'Cơm tấm',
      loggedAt: DateTime(2026, 7, 27, 12),
      mealType: MealType.lunch,
      calories: 680,
      proteinGrams: 32,
      fatGrams: 28,
      carbsGrams: 72,
      fiberGrams: 3,
      totalGrams: 350,
    );

    await state.addJournalEntry(entry, stickerBytes: Uint8List.fromList([1, 2]));

    expect(state.journalEntries.single.stickerPath, '/fake/entry-1.png');
    expect(store.saved, ['entry-1']);


    await state.removeJournalEntry('entry-1');

    expect(store.deleted, ['/fake/entry-1.png']);
    expect(state.journalEntries, isEmpty);
  });

  test('bữa ăn không có sticker thì không đụng tới kho ảnh', () async {
    final store = _RecordingStickerStore();
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
      stickerStore: store,
    );

    await state.addJournalEntry(
      JournalEntry(
        id: 'entry-2',
        dishName: 'Phở',
        loggedAt: DateTime(2026, 7, 27, 8),
        mealType: MealType.breakfast,
        calories: 400,
        proteinGrams: 20,
        fatGrams: 10,
        carbsGrams: 60,
        fiberGrams: 2,
        totalGrams: 400,
      ),
    );
    await state.removeJournalEntry('entry-2');

    expect(store.saved, isEmpty);
    expect(store.deleted, isEmpty);
  });

  test('refresh nạp lại thư mục sticker và báo cho UI dựng lại', () async {
    // Kéo xuống tải lại: ảnh sticker nằm ngoài JSON nên phải dò lại thư mục,
    // rồi báo listener để màn hình vẽ lại bằng dữ liệu vừa dò.
    final store = _RecordingStickerStore();
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
      stickerStore: store,
    );
    var notified = 0;
    state.addListener(() => notified += 1);
    expect(store.prepared, isFalse, reason: 'restore không tự nạp');

    await state.refresh();

    expect(store.prepared, isTrue);
    expect(notified, 1);
  });

  test('signing back in with the same account returns to a ready profile', () async {
    // Đăng xuất xoá hồ sơ khỏi phiên đang chạy, nhưng đăng nhập lại cùng tài
    // khoản thì phải vào thẳng màn hình chính chứ không bắt khai báo lại từ đầu.
    final storage = MemoryAppStorage();
    final auth = FakeAuthGateway();
    final state = await AppState.restore(storage, authGateway: auth);
    await state.signIn(email: 'an@example.com', password: 'mat-khau-123');
    await state.completeProfile(
      UserProfile(
        name: 'An',
        email: 'an@example.com',
        age: 25,
        heightCm: 170,
        weightKg: 65,
        targetWeightKg: 70,
        gender: 'Nam',
        activity: 'Vừa phải',
        goal: 'Tăng cân',
      ),
    );
    await state.addJournalEntry(
      JournalEntry(
        id: 'entry-1',
        dishName: 'Cơm tấm',
        loggedAt: DateTime(2026, 7, 26, 12),
        mealType: MealType.lunch,
        calories: 650,
        proteinGrams: 32,
        fatGrams: 22,
        carbsGrams: 78,
        fiberGrams: 4,
        totalGrams: 370,
      ),
    );

    await state.signOut();
    expect(state.profile, isNull, reason: 'phiên đã đăng xuất không giữ hồ sơ');

    await state.signIn(email: 'an@example.com', password: 'mat-khau-123');

    expect(state.profile?.goal, 'Tăng cân');
    expect(state.profile?.targetWeightKg, 70);
    expect(state.journalEntries.single.dishName, 'Cơm tấm');
  });

  test('signing in with a different account never inherits an old profile', () async {
    final storage = MemoryAppStorage();
    final auth = FakeAuthGateway();
    final state = await AppState.restore(storage, authGateway: auth);
    await state.signIn(email: 'an@example.com', password: 'mat-khau-123');
    await state.completeProfile(
      UserProfile(
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
    await state.signOut();

    final otherAuth = FakeAuthGateway(
      session: AuthSession(
        accessToken: 'access-token',
        refreshToken: 'refresh-token',
        expiresIn: 900,
        user: const AuthUser(
          id: 'other-id',
          email: 'binh@example.com',
          displayName: 'Bình',
          role: 'user',
        ),
      ),
    );
    final other = await AppState.restore(storage, authGateway: otherAuth);
    await other.signIn(email: 'binh@example.com', password: 'mat-khau-123');

    expect(other.profile, isNull);
    expect(other.journalEntries, isEmpty);
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
  Future<AuthSession> loginWithGoogle({required String idToken}) =>
      throw UnimplementedError();

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

class _FakeGoogleIdentityGateway implements GoogleIdentityGateway {
  _FakeGoogleIdentityGateway({this.signOutThrows = false});

  final bool signOutThrows;
  int signInCalls = 0;

  @override
  Future<String> authenticate() async {
    signInCalls += 1;
    return 'google-id-token';
  }

  @override
  Future<void> signOut() async {
    if (signOutThrows) {
      throw StateError('GoogleSignIn has not been initialized');
    }
  }
}

class _RecordingStickerStore implements StickerStore {
  final List<String> saved = [];
  final List<String> deleted = [];
  bool prepared = false;

  @override
  Future<void> prepare() async => prepared = true;

  @override
  Future<String?> save({
    required String entryId,
    required Uint8List bytes,
  }) async {
    saved.add(entryId);
    return '/fake/$entryId.png';
  }

  @override
  Future<Uint8List?> read(String? path) async => null;

  @override
  Future<void> delete(String? path) async {
    if (path != null) deleted.add(path);
  }
}
