import 'package:balance/core/state/app_state.dart';
import 'package:flutter/widgets.dart';

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({required AppState notifier, required super.child, super.key})
    : super(notifier: notifier);

  static AppState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope was not found above this context');
    return scope!.notifier!;
  }

  static AppState? maybeOf(BuildContext context) {
    return context.dependOnInheritedWidgetOfExactType<AppScope>()?.notifier;
  }
}
