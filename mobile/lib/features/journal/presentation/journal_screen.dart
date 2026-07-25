import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_bottom_bar.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/profile/presentation/profile_screen.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';

class JournalScreen extends StatelessWidget {
  const JournalScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final entries = state?.entriesForDate(DateTime.now()) ?? const [];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Nhật ký hôm nay'),
        centerTitle: true,
        backgroundColor: BalanceColors.paperBlue,
      ),
      bottomNavigationBar: BalanceBottomBar(
        currentIndex: 1,
        onHomePressed: () =>
            Navigator.of(context).popUntil((route) => route.isFirst),
        onCameraPressed: () => Navigator.of(
          context,
        ).push(MaterialPageRoute<void>(builder: (_) => const AnalyzeScreen())),
        onSuggestionsPressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const SuggestionsScreen()),
        ),
        onProfilePressed: () => Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const ProfileScreen()),
        ),
      ),
      body: GraphPaperBackground(
        child: SafeArea(
          top: false,
          child: entries.isEmpty
              ? const _EmptyJournal()
              : ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
                  children: [
                    _JournalSummary(entries: entries),
                    const SizedBox(height: 16),
                    for (final entry in entries)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Dismissible(
                          key: ValueKey(entry.id),
                          direction: DismissDirection.endToStart,
                          background: Container(
                            alignment: Alignment.centerRight,
                            padding: const EdgeInsets.only(right: 24),
                            color: Colors.redAccent,
                            child: const Icon(
                              Icons.delete,
                              color: Colors.white,
                            ),
                          ),
                          onDismissed: (_) =>
                              state?.removeJournalEntry(entry.id),
                          child: _JournalEntryCard(entry: entry),
                        ),
                      ),
                  ],
                ),
        ),
      ),
    );
  }
}

class _EmptyJournal extends StatelessWidget {
  const _EmptyJournal();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: SketchCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.menu_book_outlined, size: 58),
              SizedBox(height: 12),
              Text(
                'Chưa có bữa ăn hôm nay',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
              ),
              SizedBox(height: 6),
              Text('Chụp một món ăn rồi thêm kết quả vào nhật ký.'),
            ],
          ),
        ),
      ),
    );
  }
}

class _JournalSummary extends StatelessWidget {
  const _JournalSummary({required this.entries});

  final List<JournalEntry> entries;

  @override
  Widget build(BuildContext context) {
    final calories = entries.fold<double>(
      0,
      (sum, item) => sum + item.calories,
    );
    return SketchCard(
      color: BalanceColors.yellow,
      child: Text(
        '${entries.length} món • ${_format(calories)} kcal',
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
      ),
    );
  }
}

class _JournalEntryCard extends StatelessWidget {
  const _JournalEntryCard({required this.entry});

  final JournalEntry entry;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      child: Row(
        children: [
          const CircleAvatar(
            backgroundColor: BalanceColors.paperBlue,
            child: Icon(Icons.restaurant_rounded, color: BalanceColors.ink),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  entry.dishName,
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(
                  '${entry.mealType.label} • ${_format(entry.totalGrams)} g',
                ),
              ],
            ),
          ),
          Text(
            '${_format(entry.calories)} kcal',
            style: const TextStyle(
              color: BalanceColors.blueDark,
              fontWeight: FontWeight.w900,
            ),
          ),
        ],
      ),
    );
  }
}

String _format(double value) => value == value.roundToDouble()
    ? value.toStringAsFixed(0)
    : value.toStringAsFixed(1);
