import 'package:flutter/material.dart';

class BalancePageRoute<T> extends PageRouteBuilder<T> {
  BalancePageRoute({required WidgetBuilder builder, super.settings})
    : super(
        pageBuilder: (context, _, _) => builder(context),
        transitionDuration: _duration,
        reverseTransitionDuration: _duration,
        transitionsBuilder: (context, animation, secondaryAnimation, child) {
          if (MediaQuery.maybeOf(context)?.disableAnimations ?? false) {
            return child;
          }
          final curved = CurvedAnimation(
            parent: animation,
            curve: Curves.easeOutCubic,
            reverseCurve: Curves.easeInCubic,
          );
          return FadeTransition(
            opacity: curved,
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.025),
                end: Offset.zero,
              ).animate(curved),
              child: child,
            ),
          );
        },
      );

  static const _duration = Duration(milliseconds: 220);
}
