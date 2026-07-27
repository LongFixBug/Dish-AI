import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:balance/features/suggestions/data/suggestions_api.dart';
import 'package:balance/features/suggestions/domain/suggested_dish.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

/// Gateway giả: màn hình gọi backend thật thì test sẽ chạm mạng và treo.
class _FakeSuggestionsGateway implements SuggestionsGateway {
  _FakeSuggestionsGateway({this.dishes = const [], this.error});

  final List<SuggestedDish> dishes;
  final Object? error;
  SuggestionQuery? lastQuery;

  @override
  Future<SuggestionResult> fetch({
    required SuggestionQuery query,
    required String accessToken,
  }) async {
    lastQuery = query;
    if (error != null) throw error!;
    return SuggestionResult(
      remaining: const RemainingNutrition(
        calories: 560,
        proteinGrams: 40,
        fatGrams: 12,
        carbsGrams: 70,
      ),
      dishes: dishes,
      allergyFilterIsPartial: query.allergies.isNotEmpty,
    );
  }
}

SuggestedDish _dish(String name, double calories, {String reason = ''}) =>
    SuggestedDish(
      dishName: name,
      grams: 350,
      calories: calories,
      proteinGrams: 30,
      fatGrams: 12,
      carbsGrams: 60,
      reason: reason,
    );

Future<AppState> _signedInState() async {
  final state = await AppState.restore(
    MemoryAppStorage(),
    authGateway: FakeAuthGateway(),
  );
  await state.signIn(email: _profile.email, password: 'matkhau123');
  await state.completeProfile(_profile);
  return state;
}

Widget _app(AppState state, SuggestionsGateway gateway) => AppScope(
  notifier: state,
  child: MaterialApp(
    theme: BalanceTheme.light,
    home: SuggestionsScreen(gateway: gateway),
  ),
);

void main() {
  testWidgets('hiện gợi ý thật kèm lý do và khoảng calo còn lại', (
    tester,
  ) async {
    final gateway = _FakeSuggestionsGateway(
      dishes: [
        _dish('Ức gà áp chảo', 480, reason: 'Bù 45g đạm bạn đang thiếu'),
        _dish('Canh chua cá', 320),
      ],
    );
    await tester.pumpWidget(_app(await _signedInState(), gateway));
    await tester.pumpAndSettle();

    expect(find.text('560 kcal hôm nay'), findsOneWidget);
    expect(find.text('Ức gà áp chảo'), findsOneWidget);
    expect(find.text('480 kcal'), findsOneWidget);
    expect(find.text('Bù 45g đạm bạn đang thiếu'), findsOneWidget);
    expect(find.text('Canh chua cá'), findsOneWidget);
    expect(find.textContaining('chỉ để tham khảo'), findsOneWidget);
  });

  testWidgets('gửi kèm dị ứng và sở thích của người dùng lên máy chủ', (
    tester,
  ) async {
    // Bỏ sót bước này là gợi ý món người dùng dị ứng — lỗi gây hại thật.
    final gateway = _FakeSuggestionsGateway(dishes: [_dish('Phở gà', 400)]);
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await state.signIn(email: _profile.email, password: 'matkhau123');
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
        allergies: ['hải sản'],
      ),
    );

    await tester.pumpWidget(_app(state, gateway));
    await tester.pumpAndSettle();

    expect(gateway.lastQuery?.allergies, contains('hải sản'));
    expect(gateway.lastQuery?.preferences, isNotEmpty);
  });

  testWidgets('không còn khẩu phần thì nói rõ thay vì hiện danh sách rỗng', (
    tester,
  ) async {
    await tester.pumpWidget(
      _app(await _signedInState(), _FakeSuggestionsGateway()),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('đã ăn đủ rồi'), findsOneWidget);
  });

  testWidgets('lỗi mạng thì báo và cho thử lại', (tester) async {
    final gateway = _FakeSuggestionsGateway(
      error: const SuggestionsApiException('Không kết nối được máy chủ.'),
    );
    await tester.pumpWidget(_app(await _signedInState(), gateway));
    await tester.pumpAndSettle();

    expect(find.text('Không kết nối được máy chủ.'), findsOneWidget);
    expect(find.text('Thử lại'), findsOneWidget);
  });

  testWidgets('chạm Thêm vào nhật ký thì bữa ăn được ghi lại', (tester) async {
    final state = await _signedInState();
    final gateway = _FakeSuggestionsGateway(dishes: [_dish('Phở gà', 400)]);
    await tester.pumpWidget(_app(state, gateway));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Thêm vào nhật ký'));
    await tester.pumpAndSettle();

    expect(state.journalEntries.single.dishName, 'Phở gà');
    expect(state.journalEntries.single.calories, 400);
  });

  testWidgets('preferences can be changed and are persisted in app state', (
    tester,
  ) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await state.signIn(email: _profile.email, password: 'matkhau123');
    await state.completeProfile(_profile);
    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: SuggestionsScreen(gateway: _FakeSuggestionsGateway()),
        ),
      ),
    );

    await tester.ensureVisible(find.text('Chỉnh sửa'));
    await tester.tap(find.text('Chỉnh sửa'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(CheckboxListTile, 'Ít dầu'));
    await tester.tap(find.text('Lưu sở thích'));
    await tester.pumpAndSettle();

    expect(state.preferences, isNot(contains('Ít dầu')));
  });

  testWidgets('warns when profile has allergy or medical safety flags', (
    tester,
  ) async {
    final state = await AppState.restore(
      MemoryAppStorage(),
      authGateway: FakeAuthGateway(),
    );
    await state.signIn(email: _profile.email, password: 'matkhau123');
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
        allergies: ['đậu phộng'],
        medicalConditions: ['tiểu đường'],
      ),
    );

    await tester.pumpWidget(
      AppScope(
        notifier: state,
        child: MaterialApp(
          theme: BalanceTheme.light,
          home: SuggestionsScreen(gateway: _FakeSuggestionsGateway()),
        ),
      ),
    );

    expect(find.textContaining('chưa kiểm tra dị ứng'), findsOneWidget);
    expect(find.textContaining('bệnh nền'), findsOneWidget);
  });
}

const _profile = UserProfile(
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
