import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:flutter/material.dart';

/// A shared, paper-card notice for warnings, empty states and safe guidance.
/// Keeping it here prevents individual screens from falling back to Material
/// alert boxes that do not match Balance's notebook visual language.
class BalanceNotice extends StatelessWidget {
  const BalanceNotice({
    required this.icon,
    required this.title,
    required this.message,
    this.color,
    this.actionLabel,
    this.onAction,
    this.shadow = false,
    super.key,
  }) : assert(actionLabel == null || onAction != null);

  final IconData icon;
  final String title;
  final String message;
  final Color? color;
  final String? actionLabel;
  final VoidCallback? onAction;
  final bool shadow;

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    return SketchCard(
      color: color ?? palette.warningSurface,
      shadow: shadow,
      padding: const EdgeInsets.all(14),
      radius: 14,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: palette.ink, size: 24),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        color: palette.ink,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      message,
                      style: TextStyle(
                        color: palette.ink,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (actionLabel case final label?) ...[
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: _NoticeAction(label: label, onPressed: onAction!),
            ),
          ],
        ],
      ),
    );
  }
}

class _NoticeAction extends StatefulWidget {
  const _NoticeAction({required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  State<_NoticeAction> createState() => _NoticeActionState();
}

class _NoticeActionState extends State<_NoticeAction> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final palette = BalanceTheme.paletteOf(context);
    return Semantics(
      button: true,
      label: widget.label,
      child: Listener(
        onPointerDown: (_) => setState(() => _pressed = true),
        onPointerUp: (_) => setState(() => _pressed = false),
        onPointerCancel: (_) => setState(() => _pressed = false),
        child: GestureDetector(
          onTap: widget.onPressed,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 90),
            transform: Matrix4.translationValues(0, _pressed ? 3 : 0, 0),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: palette.surface,
              border: Border.all(color: palette.ink, width: 2),
              borderRadius: BorderRadius.circular(10),
              boxShadow: [
                BoxShadow(
                  color: palette.shadow,
                  offset: _pressed ? const Offset(1, 1) : const Offset(3, 3),
                ),
              ],
            ),
            child: Text(
              widget.label,
              style: TextStyle(
                color: palette.primaryDark,
                fontWeight: FontWeight.w900,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
