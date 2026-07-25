import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/features/auth/presentation/welcome_screen.dart';
import 'package:balance/features/dashboard/presentation/dashboard_screen.dart';
import 'package:balance/features/onboarding/presentation/profile_setup_screen.dart';
import 'package:flutter/material.dart';

class BalanceApp extends StatefulWidget {
  const BalanceApp({this.appState, super.key});

  final AppState? appState;

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
        : const DashboardScreen();
    return AppScope(
      notifier: _state,
      child: MaterialApp(
        title: 'Balance',
        debugShowCheckedModeBanner: false,
        theme: BalanceTheme.light,
        home: home,
      ),
    );
  }
}
