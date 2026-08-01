import 'package:flutter/material.dart';

/// Giữ state của các tab như [IndexedStack], nhưng chỉ để tab cũ ở lại cây
/// trong đúng thời lượng fade. Sau đó nó thành Offstage để không lộ nội dung
/// ẩn cho accessibility, test finder hay thao tác cuộn.
class FadeIndexedStack extends StatefulWidget {
  const FadeIndexedStack({
    required this.index,
    required this.children,
    super.key,
  }) : assert(index >= 0 && index < children.length);

  final int index;
  final List<Widget> children;

  @override
  State<FadeIndexedStack> createState() => _FadeIndexedStackState();
}

class _FadeIndexedStackState extends State<FadeIndexedStack>
    with SingleTickerProviderStateMixin {
  static const _duration = Duration(milliseconds: 180);

  late final AnimationController _controller;
  late int _activeIndex;
  int? _outgoingIndex;

  @override
  void initState() {
    super.initState();
    _activeIndex = widget.index;
    _controller = AnimationController(
      vsync: this,
      duration: _duration,
      value: 1,
    )..addStatusListener(_hideOutgoingTab);
  }

  @override
  void didUpdateWidget(covariant FadeIndexedStack oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.index == _activeIndex) return;

    final disabled = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    if (disabled) {
      _activeIndex = widget.index;
      _outgoingIndex = null;
      _controller.value = 1;
      return;
    }

    _outgoingIndex = _activeIndex;
    _activeIndex = widget.index;
    _controller.forward(from: 0);
  }

  void _hideOutgoingTab(AnimationStatus status) {
    if (status == AnimationStatus.completed &&
        _outgoingIndex != null &&
        mounted) {
      setState(() => _outgoingIndex = null);
    }
  }

  @override
  void dispose() {
    _controller
      ..removeStatusListener(_hideOutgoingTab)
      ..dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final entering = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeOut,
    );
    final leaving = ReverseAnimation(entering);

    return Stack(
      fit: StackFit.expand,
      children: [
        for (var itemIndex = 0; itemIndex < widget.children.length; itemIndex++)
          _TabLayer(
            key: ValueKey('fade-stack-child-$itemIndex'),
            offstage: itemIndex != _activeIndex && itemIndex != _outgoingIndex,
            active: itemIndex == _activeIndex,
            opacity: itemIndex == _activeIndex ? entering : leaving,
            child: widget.children[itemIndex],
          ),
      ],
    );
  }
}

class _TabLayer extends StatelessWidget {
  const _TabLayer({
    required this.offstage,
    required this.active,
    required this.opacity,
    required this.child,
    super.key,
  });

  final bool offstage;
  final bool active;
  final Animation<double> opacity;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Offstage(
      offstage: offstage,
      child: IgnorePointer(
        ignoring: !active,
        child: ExcludeSemantics(
          excluding: !active,
          child: TickerMode(
            enabled: active,
            child: FadeTransition(opacity: opacity, child: child),
          ),
        ),
      ),
    );
  }
}
