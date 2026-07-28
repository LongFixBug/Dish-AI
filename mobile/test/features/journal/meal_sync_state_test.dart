import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/journal/data/meal_api.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../helpers/fake_auth_gateway.dart';

void main() {
  test(
    'đồng bộ bữa đã lưu local bằng client id khi người dùng đăng nhập',
    () async {
      final gateway = _FakeMealGateway();
      final state = await AppState.restore(
        MemoryAppStorage(),
        authGateway: FakeAuthGateway(),
        mealGateway: gateway,
      );
      await state.signIn(email: 'an@example.com', password: 'matkhau123');
      final entry = _entry();

      await state.addJournalEntry(entry);
      expect(await state.syncJournalEntry(entry, source: 'analyze'), isTrue);
      expect(gateway.entries.single.id, 'entry-1');
      expect(gateway.sources.single, 'analyze');
      expect(gateway.tokens.single, 'access-token');
    },
  );

  test('mất mạng đồng bộ không làm mất nhật ký local', () async {
    final state = AppState.memory();
    final entry = _entry();

    await state.addJournalEntry(entry);

    expect(await state.syncJournalEntry(entry), isFalse);
    expect(state.journalEntries.single.id, 'entry-1');
  });
}

JournalEntry _entry() => JournalEntry(
  id: 'entry-1',
  dishName: 'Phở bò',
  loggedAt: DateTime(2026, 7, 27, 12),
  mealType: MealType.lunch,
  calories: 480,
  proteinGrams: 28,
  fatGrams: 14,
  carbsGrams: 60,
  fiberGrams: 4,
  totalGrams: 450,
);

class _FakeMealGateway implements MealGateway {
  final entries = <JournalEntry>[];
  final sources = <String>[];
  final tokens = <String>[];

  @override
  Future<void> upsert(
    JournalEntry entry, {
    required String accessToken,
    required String source,
  }) async {
    entries.add(entry);
    sources.add(source);
    tokens.add(accessToken);
  }
}
