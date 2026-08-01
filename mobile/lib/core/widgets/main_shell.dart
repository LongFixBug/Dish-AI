import 'package:balance/core/widgets/balance_bottom_bar.dart';
import 'package:balance/core/widgets/balance_page_route.dart';
import 'package:balance/core/widgets/fade_indexed_stack.dart';
import 'package:balance/features/analyze/presentation/analyze_screen.dart';
import 'package:balance/features/dashboard/presentation/dashboard_screen.dart';
import 'package:balance/features/journal/presentation/journal_screen.dart';
import 'package:balance/features/profile/presentation/profile_screen.dart';
import 'package:balance/features/suggestions/presentation/suggestions_screen.dart';
import 'package:flutter/material.dart';

/// Bốn tab chính nằm sau thanh điều hướng dưới cùng.
enum ShellTab {
  home(0),
  journal(1),
  suggestions(3),
  profile(4);

  const ShellTab(this.barIndex);

  /// Vị trí trên [BalanceBottomBar]; ô số 2 là nút chụp ảnh nên bị bỏ trống.
  final int barIndex;
}

/// Khung vỏ giữ thanh điều hướng đứng yên, chỉ đổi phần nội dung bên trên.
///
/// Trước đây mỗi tab là một màn hình riêng mang theo thanh điều hướng của
/// chính nó, và chuyển tab bằng `pushReplacement` — tức là mỗi lần bấm icon,
/// Flutter vứt cả màn hình lẫn thanh dưới đi rồi dựng lại từ đầu. Người dùng
/// nhìn thấy điều đó dưới dạng thanh dưới "nháy" một cái, còn tab cũ thì mất
/// sạch vị trí cuộn.
///
/// [IndexedStack] giữ cả bốn tab sống cùng lúc: đổi tab chỉ là đổi tab nào
/// được vẽ, nên vị trí cuộn và trạng thái của từng tab còn nguyên.
class MainShell extends StatefulWidget {
  const MainShell({this.initialTab = ShellTab.home, this.now, super.key});

  final ShellTab initialTab;

  /// Chuyển tiếp xuống trang chủ để test chốt được mốc thời gian.
  final DateTime? now;

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  late ShellTab _tab = widget.initialTab;
  int _homeAnimationSeed = 0;
  int _journalAnimationSeed = 0;
  int _suggestionsAnimationSeed = 0;
  int _profileAnimationSeed = 0;

  void _select(ShellTab tab) {
    if (_tab == tab) return;
    setState(() {
      if (tab == ShellTab.home) {
        _homeAnimationSeed += 1;
      } else if (tab == ShellTab.journal) {
        _journalAnimationSeed += 1;
      } else if (tab == ShellTab.suggestions) {
        _suggestionsAnimationSeed += 1;
      } else if (tab == ShellTab.profile) {
        _profileAnimationSeed += 1;
      }
      _tab = tab;
    });
  }

  Future<void> _openCamera() async {
    await Navigator.of(
      context,
    ).push(BalancePageRoute<void>(builder: (_) => const AnalyzeScreen()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: FadeIndexedStack(
        index: ShellTab.values.indexOf(_tab),
        children: [
          DashboardScreen(now: widget.now, animationSeed: _homeAnimationSeed),
          JournalScreen(animationSeed: _journalAnimationSeed),
          SuggestionsScreen(animationSeed: _suggestionsAnimationSeed),
          ProfileScreen(animationSeed: _profileAnimationSeed),
        ],
      ),
      bottomNavigationBar: BalanceBottomBar(
        currentIndex: _tab.barIndex,
        onHomePressed: () => _select(ShellTab.home),
        onJournalPressed: () => _select(ShellTab.journal),
        onCameraPressed: _openCamera,
        onSuggestionsPressed: () => _select(ShellTab.suggestions),
        onProfilePressed: () => _select(ShellTab.profile),
      ),
    );
  }
}
