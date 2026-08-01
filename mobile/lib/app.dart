import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/features/auth/presentation/welcome_screen.dart';
import 'package:balance/core/widgets/main_shell.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';

class BalanceApp extends StatefulWidget {
  const BalanceApp({this.appState, this.animateBackground = false, super.key});

  final AppState? appState;
  final bool animateBackground;

  @override
  State<BalanceApp> createState() => _BalanceAppState();
}

class _BalanceAppState extends State<BalanceApp> {
  late final AppState _state = widget.appState ?? AppState.memory();

  @override
  void dispose() {
    if (widget.appState == null) _state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final home = !_state.isSignedIn
        ? const WelcomeScreen()
        : _state.profile == null
        ? const ProfileSetupScreen()
        : const MainShell();
    return BalanceMotionScope(
      enabled: widget.animateBackground,
      child: AppScope(
        notifier: _state,
        child: MaterialApp(
          title: 'Balance',
          debugShowCheckedModeBanner: false,
          theme: BalanceTheme.light,
          darkTheme: BalanceTheme.dark,
          themeMode: ThemeMode.system,
          home: home,
        ),
      ),
    );
  }
}
