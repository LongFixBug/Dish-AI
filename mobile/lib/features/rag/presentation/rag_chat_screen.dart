import 'package:balance/core/state/app_scope.dart';
import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/balance_app_bar.dart';
import 'package:balance/core/widgets/graph_paper_background.dart';
import 'package:balance/core/widgets/pressable_button.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:balance/features/rag/data/rag_api.dart';
import 'package:flutter/material.dart';

/// Màn RAG V0: một câu hỏi, một câu trả lời và các tài liệu đã tham khảo.
class RagChatScreen extends StatefulWidget {
  const RagChatScreen({this.gateway, super.key});

  final RagGateway? gateway;

  @override
  State<RagChatScreen> createState() => _RagChatScreenState();
}

class _RagChatScreenState extends State<RagChatScreen> {
  final _questionController = TextEditingController();
  RagApi? _ownApi;
  RagAnswer? _result;
  String? _error;
  bool _isLoading = false;

  @override
  void dispose() {
    _questionController.dispose();
    _ownApi?.close();
    super.dispose();
  }

  Future<void> _ask() async {
    final question = _questionController.text.trim();
    if (question.isEmpty) {
      setState(() => _error = 'Hãy nhập câu hỏi trước.');
      return;
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final state = AppScope.maybeOf(context);
      if (state == null) {
        throw const RagApiException('Chưa đăng nhập.');
      }
      final token = await state.validAccessToken();
      final gateway = widget.gateway ?? (_ownApi ??= RagApi());
      final result = await gateway.ask(question: question, accessToken: token);
      if (!mounted) return;
      setState(() => _result = result);
    } on RagApiException catch (error) {
      if (!mounted) return;
      setState(() => _error = error.message);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Có lỗi không mong muốn. Hãy thử lại.');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const BalanceAppBar(
        title: 'Hỏi FoodAI',
        subtitle: 'Trả lời từ tài liệu đã nạp',
      ),
      body: GraphPaperBackground(
        child: SafeArea(
          top: false,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
            children: [
              const _IntroCard(),
              const SizedBox(height: 12),
              _QuestionInput(
                controller: _questionController,
                isLoading: _isLoading,
                onAsk: _ask,
              ),
              if (_error case final error?) ...[
                const SizedBox(height: 12),
                _ErrorCard(message: error),
              ],
              if (_isLoading) ...[
                const SizedBox(height: 18),
                const Center(child: CircularProgressIndicator()),
              ],
              if (_result case final result?) ...[
                const SizedBox(height: 14),
                _AnswerCard(result: result),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _IntroCard extends StatelessWidget {
  const _IntroCard();

  @override
  Widget build(BuildContext context) {
    return const SketchCard(
      color: Color(0xFFE8F4FF),
      padding: EdgeInsets.all(14),
      child: Row(
        children: [
          Icon(Icons.auto_awesome_rounded, color: BalanceColors.blueDark),
          SizedBox(width: 10),
          Expanded(
            child: Text(
              'Hỏi về kiến thức FoodAI. Câu trả lời luôn kèm tài liệu nguồn.',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _QuestionInput extends StatelessWidget {
  const _QuestionInput({
    required this.controller,
    required this.isLoading,
    required this.onAsk,
  });

  final TextEditingController controller;
  final bool isLoading;
  final Future<void> Function() onAsk;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: controller,
            enabled: !isLoading,
            minLines: 2,
            maxLines: 4,
            maxLength: 1000,
            textInputAction: TextInputAction.send,
            onSubmitted: (_) {
              if (!isLoading) onAsk();
            },
            decoration: const InputDecoration(
              hintText: 'Ví dụ: Phở bò thường có những thành phần gì?',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 10),
          PressableButton(
            label: isLoading ? 'FoodAI đang tìm...' : 'Hỏi FoodAI',
            icon: Icons.send_rounded,
            backgroundColor: BalanceColors.blue,
            onPressed: isLoading ? null : () => onAsk(),
          ),
        ],
      ),
    );
  }
}

class _AnswerCard extends StatelessWidget {
  const _AnswerCard({required this.result});

  final RagAnswer result;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: const Color(0xFFFFFCF4),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'FoodAI trả lời',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Text(result.answer),
          const SizedBox(height: 14),
          const Text(
            'Nguồn đã dùng',
            style: TextStyle(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          ...result.sources.map(
            (source) => Padding(
              padding: const EdgeInsets.only(bottom: 5),
              child: Text(
                '• ${source.title} · ${source.source} '
                '(độ liên quan ${(source.score * 100).toStringAsFixed(1)}%)',
                style: const TextStyle(color: BalanceColors.muted),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  const _ErrorCard({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return SketchCard(
      color: const Color(0xFFFFE8E3),
      padding: const EdgeInsets.all(14),
      child: Text(
        message,
        style: const TextStyle(
          color: Color(0xFF8A1D12),
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
