import 'dart:async';

import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/theme/balance_theme.dart';
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
          _lines[index] = _lines[index].withText(_lines[index].text + text);
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Hỏi Balance'),
        actions: [
          if (_sending)
            IconButton(
              tooltip: 'Dừng',
              onPressed: _stop,
              icon: const Icon(Icons.stop_circle_outlined),
            ),
        ],
      ),
      body: Column(
        children: [
          if (hasSafetyFlags) const _SafetyNotice(),
          Expanded(
            child: _lines.isEmpty
                ? _EmptyChat(onPrompt: _send)
                : ListView.builder(
                    controller: _scroll,
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
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
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _input,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.newline,
                      decoration: const InputDecoration(
                        hintText: 'Hỏi về nhật ký hoặc món ăn…',
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _sending ? null : _send,
                    icon: const Icon(Icons.arrow_upward_rounded),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat({required this.onPrompt});

  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 42, 20, 20),
      children: [
        const Icon(
          Icons.chat_bubble_outline_rounded,
          size: 52,
          color: BalanceColors.blueDark,
        ),
        const SizedBox(height: 12),
        Text(
          'Mình có thể giúp bạn đọc nhật ký và tìm thông tin dinh dưỡng.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 22),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          alignment: WrapAlignment.center,
          children: [
            for (final prompt in _ChatScreenState._suggestedPrompts)
              ActionChip(
                label: Text(prompt),
                onPressed: () => onPrompt(prompt),
              ),
          ],
        ),
      ],
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
      child: Container(
        constraints: const BoxConstraints(maxWidth: 330),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: user ? BalanceColors.blueDark : BalanceColors.paperBlue,
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              text,
              style: TextStyle(
                color: user ? Colors.white : BalanceColors.ink,
                fontWeight: FontWeight.w600,
              ),
            ),
            if (!user && sources.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Nguồn: ${sources.join(', ')}',
                style: const TextStyle(
                  color: BalanceColors.blueDark,
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ],
        ),
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
    return Container(
      width: double.infinity,
      color: const Color(0xFFFFF1C7),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: const Text(
        'Thông tin chỉ mang tính tham khảo. Nếu bạn có bệnh nền hoặc dị ứng, '
        'hãy hỏi chuyên gia; Balance không xác nhận món nào an toàn.',
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
      ),
    );
  }
}
