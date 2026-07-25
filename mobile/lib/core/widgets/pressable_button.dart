import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class PressableButton extends StatefulWidget {
  const PressableButton({
    required this.label,
    required this.onPressed,
    this.backgroundColor = BalanceColors.blue,
    this.foregroundColor = Colors.white,
    this.icon,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final Color backgroundColor;
  final Color foregroundColor;
  final IconData? icon;

  @override
  State<PressableButton> createState() => _PressableButtonState();
}

class _PressableButtonState extends State<PressableButton> {
  static const _travel = 6.0;
  bool _isPressed = false;

  void _setPressed(bool value) {
    if (widget.onPressed == null || _isPressed == value) return;
    setState(() => _isPressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;

    return Semantics(
      button: true,
      enabled: enabled,
      child: Listener(
        onPointerDown: enabled ? (_) => _setPressed(true) : null,
        onPointerUp: enabled ? (_) => _setPressed(false) : null,
        onPointerCancel: enabled ? (_) => _setPressed(false) : null,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.onPressed,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 90),
            curve: Curves.easeOut,
            transform: Matrix4.translationValues(
              0,
              _isPressed ? _travel : 0,
              0,
            ),
            height: 58,
            width: double.infinity,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: enabled
                  ? widget.backgroundColor
                  : widget.backgroundColor.withValues(alpha: 0.45),
              border: Border.all(color: BalanceColors.ink, width: 2.5),
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(
                  color: BalanceColors.ink,
                  offset: _isPressed ? const Offset(1, 1) : const Offset(5, 6),
                ),
              ],
            ),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (widget.icon != null) ...[
                    Icon(widget.icon, color: widget.foregroundColor, size: 23),
                    const SizedBox(width: 10),
                  ],
                  Flexible(
                    child: FittedBox(
                      fit: BoxFit.scaleDown,
                      child: Text(
                        widget.label,
                        maxLines: 1,
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(
                              color: widget.foregroundColor,
                              fontSize: 18,
                            ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
