import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/analyze/domain/analyze_result.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('profile, session and journal survive an app restart', () async {
    final storage = MemoryAppStorage();
    final state = await AppState.restore(storage);
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

    await state.signIn(email: profile.email);
    await state.completeProfile(profile);
    await state.addJournalEntry(
      JournalEntry.fromAnalysis(
        result: result,
        loggedAt: DateTime(2026, 7, 25, 12),
        mealType: MealType.lunch,
      ),
    );

    final restored = await AppState.restore(storage);
    expect(restored.isSignedIn, isTrue);
    expect(restored.profile, profile);
    expect(restored.journalEntries.single.dishName, 'Cơm tấm');
    expect(restored.todayCalories(DateTime(2026, 7, 25)), 650);
  });

  test('sign out keeps local data but closes the active session', () async {
    final storage = MemoryAppStorage();
    final state = await AppState.restore(storage);

    await state.signIn(email: 'an@example.com');
    await state.signOut();

    final restored = await AppState.restore(storage);
    expect(restored.isSignedIn, isFalse);
  });
}
