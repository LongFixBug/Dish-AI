import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';

class BalanceBackButton extends StatelessWidget {
  const BalanceBackButton({super.key});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 8),
      child: BalanceIconButton(
        tooltip: 'Quay lại',
        icon: Icons.arrow_back_rounded,
        onPressed: () => Navigator.of(context).maybePop(),
      ),
    );
  }
}

class BalanceIconButton extends StatefulWidget {
  const BalanceIconButton({
    required this.tooltip,
    required this.icon,
    this.onPressed,
    super.key,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  State<BalanceIconButton> createState() => _BalanceIconButtonState();
}

class _BalanceIconButtonState extends State<BalanceIconButton> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (widget.onPressed == null || _pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null;
    final palette = BalanceTheme.paletteOf(context);
    return Tooltip(
      message: widget.tooltip,
      child: Semantics(
        button: true,
        enabled: enabled,
        label: widget.tooltip,
        child: Listener(
          onPointerDown: enabled ? (_) => _setPressed(true) : null,
          onPointerUp: enabled ? (_) => _setPressed(false) : null,
          onPointerCancel: enabled ? (_) => _setPressed(false) : null,
          child: GestureDetector(
            onTap: widget.onPressed,
            child: AnimatedContainer(
              key: ValueKey('balance-icon-button-${widget.tooltip}'),
              duration: const Duration(milliseconds: 140),
              transform: Matrix4.translationValues(0, _pressed ? 4 : 0, 0),
              width: 44,
              height: 44,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: enabled
                    ? palette.surface
                    : palette.surface.withValues(alpha: 0.62),
                border: Border.all(
                  color: palette.ink,
                  width: BalanceStrokes.strong,
                ),
                borderRadius: BorderRadius.circular(15),
                boxShadow: [
                  BoxShadow(
                    color: palette.shadow.withValues(
                      alpha: enabled ? 0.2 : 0.08,
                    ),
                    offset: _pressed ? const Offset(0, 1) : const Offset(0, 5),
                    blurRadius: 0,
                  ),
                ],
              ),
              child: Icon(
                widget.icon,
                color: enabled ? palette.ink : palette.muted,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class BalanceAppBar extends StatelessWidget implements PreferredSizeWidget {
  const BalanceAppBar({
    required this.title,
    this.subtitle,
    this.actions,
    this.showBackButton = true,
    super.key,
  });

  final String title;
  final String? subtitle;
  final List<Widget>? actions;
  final bool showBackButton;

  @override
  Size get preferredSize => Size.fromHeight(subtitle == null ? 60 : 68);

  @override
  Widget build(BuildContext context) {
    final canPop = Navigator.of(context).canPop();
    final palette = BalanceTheme.paletteOf(context);
    return AppBar(
      automaticallyImplyLeading: false,
      leading: showBackButton && canPop ? const BalanceBackButton() : null,
      title: subtitle == null
          ? Text(title)
          : Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(title),
                Text(
                  subtitle!,
                  style: TextStyle(
                    color: palette.muted,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
      centerTitle: true,
      backgroundColor: palette.background.withValues(alpha: 0.96),
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      actions: actions,
    );
  }
}
