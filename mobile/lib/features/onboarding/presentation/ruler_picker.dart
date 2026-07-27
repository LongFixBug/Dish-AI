import 'package:balance/core/theme/balance_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Thước kéo ngang: kim luôn đứng yên giữa, dải vạch số trượt qua dưới kim.
///
/// Khác Slider ở chỗ người dùng không phải nhắm trúng một cái nút bé xíu —
/// quẹt vào bất kỳ đâu trên thước là kéo được, giống xoay núm cân cơ.
class RulerPicker extends StatefulWidget {
  const RulerPicker({
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    this.height = 74,
    this.tickSpacing = 12,
    super.key,
  });

  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;
  final double height;

  /// Khoảng cách giữa hai vạch liền nhau, tính bằng pixel.
  final double tickSpacing;

  @override
  State<RulerPicker> createState() => _RulerPickerState();
}

class _RulerPickerState extends State<RulerPicker> {
  ScrollController? _controller;
  double _viewportWidth = 0;

  /// Giá trị mà thước đang tự cuộn tới. Dùng để bỏ qua tiếng vọng: mỗi lần
  /// widget nhận value mới từ cha, ta animate tới đó và KHÔNG được coi các
  /// khung hình trung gian của animation là người dùng đang kéo.
  int? _animatingTo;

  /// Đang trong một lượt lướt của người dùng (tính cả quãng trôi sau khi nhấc
  /// tay). Trong lúc này tuyệt đối không được animateTo: mỗi lần giá trị đổi,
  /// cha gọi setState và nếu ta animate theo thì đà trượt bị giết ngay, kéo cả
  /// màn hình chỉ nhích được đúng một vạch.
  bool _isUserScrolling = false;

  int get _clampedValue => widget.value.clamp(widget.min, widget.max);

  double _offsetFor(int value) => (value - widget.min) * widget.tickSpacing;

  void _ensureController(double viewportWidth) {
    if (_controller != null && _viewportWidth == viewportWidth) return;
    _viewportWidth = viewportWidth;
    _controller?.dispose();
    _controller = ScrollController(
      initialScrollOffset: _offsetFor(_clampedValue),
    );
  }

  @override
  void didUpdateWidget(RulerPicker oldWidget) {
    super.didUpdateWidget(oldWidget);
    final controller = _controller;
    if (controller == null || !controller.hasClients) return;
    if (widget.value == oldWidget.value) return;
    if (_isUserScrolling) return;
    final target = _offsetFor(_clampedValue);
    if ((controller.offset - target).abs() < 0.5) return;
    _animatingTo = _clampedValue;
    controller.animateTo(
      target,
      duration: const Duration(milliseconds: 180),
      curve: Curves.easeOut,
    );
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  bool _onScroll(ScrollNotification notification) {
    final controller = _controller;
    if (controller == null || !controller.hasClients) return false;
    if (notification is ScrollStartNotification) _isUserScrolling = true;

    final raw = controller.offset / widget.tickSpacing + widget.min;
    final next = raw.round().clamp(widget.min, widget.max);
    if (next != _animatingTo && next != widget.value) {
      _animatingTo = null;
      HapticFeedback.selectionClick();
      widget.onChanged(next);
    }

    if (notification is ScrollEndNotification) {
      _isUserScrolling = false;
      _animatingTo = null;
      _snapToTick(next);
    }
    return false;
  }

  /// Dừng giữa hai vạch thì gí về vạch gần nhất, để con số hiển thị luôn khớp
  /// với vạch đang nằm dưới kim.
  void _snapToTick(int value) {
    final controller = _controller;
    if (controller == null || !controller.hasClients) return;
    final target = _offsetFor(value);
    if ((controller.offset - target).abs() <= 0.5) return;
    _animatingTo = value;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final live = _controller;
      if (live == null || !live.hasClients) return;
      live.animateTo(
        target,
        duration: const Duration(milliseconds: 140),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: widget.height,
      child: LayoutBuilder(
        builder: (context, constraints) {
          _ensureController(constraints.maxWidth);
          final sidePadding = constraints.maxWidth / 2;
          return Stack(
            alignment: Alignment.center,
            children: [
              NotificationListener<ScrollNotification>(
                onNotification: _onScroll,
                child: ListView.builder(
                  controller: _controller,
                  scrollDirection: Axis.horizontal,
                  physics: const BouncingScrollPhysics(),
                  padding: EdgeInsets.symmetric(horizontal: sidePadding),
                  itemCount: widget.max - widget.min + 1,
                  itemExtent: widget.tickSpacing,
                  itemBuilder: (context, index) =>
                      _Tick(value: widget.min + index),
                ),
              ),
              IgnorePointer(child: _Needle(height: widget.height)),
            ],
          );
        },
      ),
    );
  }
}

class _Tick extends StatelessWidget {
  const _Tick({required this.value});

  final int value;

  @override
  Widget build(BuildContext context) {
    final isMajor = value % 10 == 0;
    final isMedium = value % 5 == 0;
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Container(
          width: isMajor ? 2.5 : 1.5,
          height: isMajor
              ? 26
              : isMedium
              ? 18
              : 11,
          color: isMajor ? BalanceColors.ink : BalanceColors.muted,
        ),
        SizedBox(
          height: 22,
          child: isMajor
              ? Padding(
                  padding: const EdgeInsets.only(top: 4),
                  // Ô mỗi vạch chỉ rộng bằng tickSpacing nên "170" sẽ bị xén
                  // còn "17"; OverflowBox cho nhãn tràn ra hai bên vạch.
                  child: OverflowBox(
                    maxWidth: 60,
                    child: Text(
                      '$value',
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                )
              : null,
        ),
      ],
    );
  }
}

class _Needle extends StatelessWidget {
  const _Needle({required this.height});

  final double height;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: const BoxDecoration(
            color: BalanceColors.blue,
            shape: BoxShape.circle,
          ),
        ),
        Container(width: 3.5, height: 34, color: BalanceColors.blue),
        const SizedBox(height: 22),
      ],
    );
  }
}
