import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class PressableButton extends StatefulWidget {
  const PressableButton({
    required this.label,
    required this.onPressed,
    this.backgroundColor,
    this.foregroundColor = Colors.white,
    this.icon,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final Color? backgroundColor;
  final Color foregroundColor;
  final IconData? icon;

  @override
  State<PressableButton> createState() => _PressableButtonState();
}

class _PressableButtonState extends State<PressableButton> {
  static const _travel = 4.0;
  bool _isPressed = false;

  void _setPressed(bool value) {
    if (widget.onPressed == null || _isPressed == value) return;
    setState(() => _isPressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final palette = BalanceTheme.paletteOf(context);
    final backgroundColor = widget.backgroundColor ?? palette.primary;

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
            duration: const Duration(milliseconds: 100),
            // BoxShadow không chấp nhận blur âm; các curve overshoot như
            // easeOutBack có thể nội suy qua 0 khi nút nhả, nên giữ cubic.
            curve: Curves.easeOutCubic,
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
                  ? backgroundColor
                  : backgroundColor.withValues(alpha: 0.45),
              border: Border.all(
                color: palette.ink,
                width: BalanceStrokes.strong,
              ),
              borderRadius: BorderRadius.circular(BalanceRadii.control),
              boxShadow: [
                if (!_isPressed)
                  BoxShadow(
                    color: palette.shadow,
                    offset: const Offset(4, 5),
                    blurRadius: 0,
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
