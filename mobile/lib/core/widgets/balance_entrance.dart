import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:flutter/material.dart';

class BalanceEntrance extends StatelessWidget {
  const BalanceEntrance({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return BalanceScreenMotion(child: child);
  }
}
