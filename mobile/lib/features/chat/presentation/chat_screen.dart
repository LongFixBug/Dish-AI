import 'dart:async';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/balance_screen_motion.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/chat/data/chat_api.dart';
import 'package:flutter/material.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({this.api, super.key});

  final ChatApi? api;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatLine {
  const _ChatLine({
    required this.role,
    required this.text,
    this.sources = const [],
  });

  final String role;
  final String text;
  final List<String> sources;

  _ChatLine withText(String value) =>
      _ChatLine(role: role, text: value, sources: sources);

  _ChatLine withSources(List<String> value) =>
      _ChatLine(role: role, text: text, sources: List.unmodifiable(value));
}

String _plainChatText(String value) =>
    value.replaceAll('**', '').replaceAll('__', '');

class _ChatScreenState extends State<ChatScreen> {
  static const _suggestedPrompts = [
    'Hôm qua bữa trưa tôi ăn gì?',
    'Tuần này tôi nạp bao nhiêu calo?',
    'Phở bò khác bún bò thế nào?',
  ];

  late final ChatApi _api = widget.api ?? ChatApi();
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _lines = <_ChatLine>[];
  StreamSubscription<ChatEvent>? _subscription;
  bool _sending = false;
  int? _assistantIndex;
  int _requestSerial = 0;

  @override
  void dispose() {
    _subscription?.cancel();
    _input.dispose();
    _scroll.dispose();
    if (widget.api == null) _api.close();
    super.dispose();
  }

  void _send([String? preset]) {
    if (_sending) return;
    final message = (preset ?? _input.text).trim();
    if (message.isEmpty) return;
    final state = AppScope.maybeOf(context);
    if (state == null) return;

    _input.clear();
    setState(() {
      _lines
        ..add(_ChatLine(role: 'user', text: message))
        ..add(const _ChatLine(role: 'assistant', text: ''));
      if (_lines.length > 100) {
        _lines.removeRange(0, _lines.length - 100);
      }
      _sending = true;
      _assistantIndex = _lines.length - 1;
    });
    _scrollToEnd();

    final assistantIndex = _assistantIndex!;
    final requestSerial = ++_requestSerial;
    final history = _lines
        .take(assistantIndex - 1)
        .where((line) => line.text.isNotEmpty)
        .toList(growable: false)
        .reversed
        .take(12)
        .toList()
        .reversed
        .map((line) => ChatMessagePayload(role: line.role, content: line.text))
        .toList(growable: false);

    unawaited(_startStream(state, message, history, requestSerial));
  }

  Future<void> _startStream(
    AppState state,
    String message,
    List<ChatMessagePayload> history,
    int requestSerial,
  ) async {
    try {
      final accessToken = await state.validAccessToken();
      if (!mounted || requestSerial != _requestSerial) return;
      _subscription = _api
          .streamChat(
            message: message,
            history: history,
            accessToken: accessToken,
          )
          .listen(
            (event) => _handleEvent(requestSerial, event),
            onError: (Object error, StackTrace stackTrace) =>
                _handleError(requestSerial, error, stackTrace),
            onDone: () => _finish(requestSerial),
          );
    } on Object catch (error, stackTrace) {
      _handleError(requestSerial, error, stackTrace);
    }
  }

  void _handleEvent(int requestSerial, ChatEvent event) {
    if (!mounted || requestSerial != _requestSerial) return;
    final index = _assistantIndex;
    if (index == null || index >= _lines.length) return;
    if (event.name == 'delta') {
      final text = event.data['text'];
      if (text is String) {
        setState(() {
          _lines[index] = _lines[index].withText(
            _plainChatText(_lines[index].text + text),
          );
        });
        _scrollToEnd();
      }
    } else if (event.name == 'sources' || event.name == 'meta') {
      final items = event.name == 'sources'
          ? event.data['items']
          : event.data['sources'];
      final sources = _sourceLabels(items);
      if (sources.isNotEmpty) {
        setState(() {
          _lines[index] = _lines[index].withSources(sources);
        });
        _scrollToEnd();
      }
    } else if (event.name == 'error') {
      final message = event.data['message'];
      if (message is String) {
        setState(() => _lines[index] = _lines[index].withText(message));
      }
    }
  }

  void _handleError(int requestSerial, Object error, StackTrace _) {
    if (!mounted || requestSerial != _requestSerial) return;
    final message = error is ChatApiException
        ? error.message
        : 'Chatbot tạm thời gặp lỗi. Hãy thử lại nhé.';
    final index = _assistantIndex;
    setState(() {
      if (index != null && index < _lines.length) {
        _lines[index] = _lines[index].withText(message);
      }
      _sending = false;
    });
  }

  void _finish(int requestSerial) {
    if (!mounted || requestSerial != _requestSerial) return;
    setState(() => _sending = false);
    _subscription = null;
  }

  Future<void> _stop() async {
    _requestSerial++;
    final subscription = _subscription;
    _subscription = null;
    await subscription?.cancel();
    if (!mounted) return;
    setState(() => _sending = false);
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.maybeOf(context);
    final hasSafetyFlags = state?.profile?.hasNutritionSafetyFlags ?? false;
    return BalanceScreenMotion(
      child: Scaffold(
        appBar: BalanceAppBar(
          title: 'Hỏi Balance',
          subtitle: 'Trợ lý dinh dưỡng',
          actions: [
            if (_sending)
              Padding(
                padding: const EdgeInsets.only(right: 10),
                child: BalanceIconButton(
                  tooltip: 'Dừng',
                  icon: Icons.stop_rounded,
                  onPressed: _stop,
                ),
              ),
          ],
        ),
        body: GraphPaperBackground(
          child: SafeArea(
            top: false,
            child: Column(
              children: [
                if (hasSafetyFlags)
                  const Padding(
                    padding: EdgeInsets.fromLTRB(16, 12, 16, 0),
                    child: BalanceReveal(index: 0, child: _SafetyNotice()),
                  ),
                Expanded(
                  child: BalanceReveal(
                    index: hasSafetyFlags ? 1 : 0,
                    child: AnimatedSwitcher(
                      duration: const Duration(milliseconds: 220),
                      switchInCurve: Curves.easeOutCubic,
                      switchOutCurve: Curves.easeInCubic,
                      child: _lines.isEmpty
                          ? _EmptyChat(
                              key: const ValueKey('empty-chat'),
                              onPrompt: _send,
                            )
                          : ListView.builder(
                              key: const ValueKey('chat-history'),
                              controller: _scroll,
                              padding: const EdgeInsets.fromLTRB(
                                16,
                                18,
                                16,
                                12,
                              ),
                              itemCount: _lines.length,
                              itemBuilder: (context, index) {
                                final line = _lines[index];
                                return _Bubble(
                                  role: line.role,
                                  text: line.text.isEmpty && _sending
                                      ? 'Đang tìm dữ liệu…'
                                      : line.text,
                                  sources: line.sources,
                                );
                              },
                            ),
                    ),
                  ),
                ),
                BalanceReveal(
                  index: hasSafetyFlags ? 2 : 1,
                  child: _ChatComposer(
                    controller: _input,
                    sending: _sending,
                    onSend: _send,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat({required this.onPrompt, super.key});

  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 22, 16, 20),
      children: [
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 620),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                BalanceReveal(
                  index: 1,
                  child: SketchCard(
                    color: const Color(0xFFFFFAF0),
                    padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
                    child: Row(
                      children: [
                        Container(
                          width: 56,
                          height: 56,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(
                            color: BalanceColors.yellow,
                            border: Border.all(
                              color: BalanceColors.ink.withValues(alpha: 0.72),
                              width: BalanceStrokes.regular,
                            ),
                            borderRadius: BorderRadius.circular(18),
                          ),
                          child: const Icon(
                            Icons.auto_awesome_rounded,
                            color: BalanceColors.ink,
                            size: 29,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Hỏi Balance',
                                style: Theme.of(context).textTheme.titleLarge,
                              ),
                              const SizedBox(height: 3),
                              Text(
                                'Hỏi nhanh về nhật ký, món ăn và dinh dưỡng.',
                                style: Theme.of(context).textTheme.bodyMedium,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                BalanceReveal(
                  index: 2,
                  child: Text(
                    'Gợi ý để bắt đầu',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                const SizedBox(height: 10),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final twoColumns = constraints.maxWidth >= 560;
                    final width = twoColumns
                        ? (constraints.maxWidth - 10) / 2
                        : constraints.maxWidth;
                    return Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        for (
                          var i = 0;
                          i < _ChatScreenState._suggestedPrompts.length;
                          i++
                        )
                          SizedBox(
                            width: width,
                            child: BalanceReveal(
                              index: 3 + i,
                              child: _PromptCard(
                                prompt: _ChatScreenState._suggestedPrompts[i],
                                onPressed: () => onPrompt(
                                  _ChatScreenState._suggestedPrompts[i],
                                ),
                              ),
                            ),
                          ),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _PromptCard extends StatelessWidget {
  const _PromptCard({required this.prompt, required this.onPressed});

  final String prompt;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: prompt,
      child: GestureDetector(
        onTap: onPressed,
        child: SketchCard(
          color: BalanceColors.paper,
          radius: BalanceRadii.control,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
          child: Row(
            children: [
              Container(
                width: 30,
                height: 30,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: BalanceColors.mint.withValues(alpha: 0.5),
                  border: Border.all(
                    color: BalanceColors.ink.withValues(alpha: 0.44),
                    width: 1,
                  ),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.north_east_rounded,
                  size: 18,
                  color: BalanceColors.blueDark,
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Text(
                  prompt,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({
    required this.role,
    required this.text,
    required this.sources,
  });

  final String role;
  final String text;
  final List<String> sources;

  @override
  Widget build(BuildContext context) {
    final user = role == 'user';
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 330),
        child: Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: SketchCard(
            color: user ? BalanceColors.blueDark : BalanceColors.paper,
            radius: 18,
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      user
                          ? Icons.person_outline_rounded
                          : Icons.auto_awesome_rounded,
                      size: 15,
                      color: user ? Colors.white : BalanceColors.blueDark,
                    ),
                    const SizedBox(width: 5),
                    Text(
                      user ? 'BẠN' : 'BALANCE',
                      style: TextStyle(
                        color: user ? Colors.white : BalanceColors.blueDark,
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  text,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: user ? Colors.white : BalanceColors.ink,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (!user && sources.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  _SourceNote(sources: sources),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SourceNote extends StatelessWidget {
  const _SourceNote({required this.sources});

  final List<String> sources;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
      decoration: BoxDecoration(
        color: BalanceColors.paperBlue,
        border: Border.all(color: BalanceColors.ink, width: 1.5),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.menu_book_outlined,
            color: BalanceColors.blueDark,
            size: 16,
          ),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              'Nguồn: ${sources.join(', ')}',
              style: const TextStyle(
                color: BalanceColors.blueDark,
                fontSize: 11,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

List<String> _sourceLabels(Object? rawItems) {
  if (rawItems is! List) return const [];
  final labels = <String>[];
  for (final raw in rawItems) {
    if (raw is! Map) continue;
    final label = raw['label'];
    final source = raw['source'];
    if (label is! String || label.trim().isEmpty) continue;
    final cleanLabel = label.trim();
    final cleanSource = source is String ? source.trim() : '';
    labels.add(cleanSource.isEmpty ? cleanLabel : '$cleanLabel ($cleanSource)');
  }
  return labels;
}

class _SafetyNotice extends StatelessWidget {
  const _SafetyNotice();

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: const Color(0xFFFFF1C7),
      radius: 13,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.health_and_safety_outlined, size: 20),
          SizedBox(width: 9),
          Expanded(
            child: Text(
              'Thông tin chỉ mang tính tham khảo. Nếu bạn có bệnh nền hoặc dị ứng, '
              'hãy hỏi chuyên gia; Balance không xác nhận món nào an toàn.',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatComposer extends StatelessWidget {
  const _ChatComposer({
    required this.controller,
    required this.sending,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 6, 16, 14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: Container(
                constraints: const BoxConstraints(minHeight: 58),
                decoration: BoxDecoration(
                  color: BalanceColors.paper,
                  border: Border.all(
                    color: BalanceColors.ink.withValues(alpha: 0.58),
                    width: BalanceStrokes.regular,
                  ),
                  borderRadius: BorderRadius.circular(BalanceRadii.control),
                  boxShadow: const [BalanceShadows.card],
                ),
                child: TextField(
                  controller: controller,
                  minLines: 1,
                  maxLines: 4,
                  textInputAction: TextInputAction.newline,
                  keyboardType: TextInputType.multiline,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyLarge?.copyWith(fontWeight: FontWeight.w700),
                  decoration: const InputDecoration(
                    hintText: 'Hỏi về nhật ký hoặc món ăn…',
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    filled: false,
                    contentPadding: EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 14,
                    ),
                  ),
                  onSubmitted: (_) => onSend(),
                ),
              ),
            ),
            const SizedBox(width: 10),
            _RaisedSendButton(enabled: !sending, onPressed: onSend),
          ],
        ),
      ),
    );
  }
}

class _RaisedSendButton extends StatefulWidget {
  const _RaisedSendButton({required this.enabled, required this.onPressed});

  final bool enabled;
  final VoidCallback onPressed;

  @override
  State<_RaisedSendButton> createState() => _RaisedSendButtonState();
}

class _RaisedSendButtonState extends State<_RaisedSendButton> {
  bool _pressed = false;

  void _setPressed(bool value) {
    if (!widget.enabled || _pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      enabled: widget.enabled,
      label: 'Gửi câu hỏi',
      child: Listener(
        onPointerDown: widget.enabled ? (_) => _setPressed(true) : null,
        onPointerUp: widget.enabled ? (_) => _setPressed(false) : null,
        onPointerCancel: widget.enabled ? (_) => _setPressed(false) : null,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTap: widget.enabled ? widget.onPressed : null,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 140),
            curve: Curves.easeOutCubic,
            transform: Matrix4.translationValues(0, _pressed ? 5 : 0, 0),
            width: 58,
            height: 58,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: widget.enabled
                  ? BalanceColors.blue
                  : BalanceColors.blue.withValues(alpha: 0.42),
              border: Border.all(
                color: BalanceColors.ink.withValues(alpha: 0.82),
                width: BalanceStrokes.strong,
              ),
              borderRadius: BorderRadius.circular(16),
              boxShadow: [
                BoxShadow(
                  color: BalanceColors.ink.withValues(alpha: 0.22),
                  offset: _pressed ? const Offset(0, 1) : const Offset(0, 6),
                  blurRadius: _pressed ? 2 : 11,
                ),
              ],
            ),
            child: const Icon(
              Icons.arrow_upward_rounded,
              color: Colors.white,
              size: 27,
            ),
          ),
        ),
      ),
    );
  }
}
