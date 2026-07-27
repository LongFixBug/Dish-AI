import 'package:balance/core/theme/balance_theme.dart';
import 'package:balance/core/widgets/sketch_card.dart';
import 'package:flutter/material.dart';

/// Kết quả một lượt đánh giá nhanh của người dùng.
enum QuickVerdict { none, good, wrong, thanks }

/// Ô hỏi "nhận diện có đúng không" ngay dưới kết quả.
///
/// Đây là vòng phản hồi rẻ nhất để mô hình khá lên: người dùng chỉ mất một
/// cú chạm, và khi họ bảo sai thì mới hỏi thêm tên món đúng.
class QuickFeedbackCard extends StatelessWidget {
  const QuickFeedbackCard({
    required this.verdict,
    required this.onGood,
    required this.onWrong,
    super.key,
  });

  final QuickVerdict verdict;
  final VoidCallback onGood;
  final VoidCallback onWrong;

  @override
  Widget build(BuildContext context) {
    if (verdict == QuickVerdict.thanks || verdict == QuickVerdict.good) {
      return SketchCard(
        shadow: false,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          children: [
            const Icon(Icons.favorite_rounded, color: BalanceColors.orange),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                verdict == QuickVerdict.good
                    ? 'Cảm ơn bạn! Balance sẽ giữ cách nhận diện này.'
                    : 'Đã ghi nhận. Góp ý của bạn giúp lần sau đoán đúng hơn.',
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
      );
    }

    return SketchCard(
      shadow: false,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(
        children: [
          const Expanded(
            child: Text(
              'Balance nhận diện đúng chưa?',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
            ),
          ),
          _VerdictButton(
            key: const ValueKey('feedback-good'),
            icon: Icons.thumb_up_outlined,
            tooltip: 'Nhận diện đúng',
            onPressed: onGood,
          ),
          const SizedBox(width: 8),
          _VerdictButton(
            key: const ValueKey('feedback-wrong'),
            icon: Icons.thumb_down_outlined,
            tooltip: 'Nhận diện sai',
            onPressed: onWrong,
          ),
        ],
      ),
    );
  }
}

class _VerdictButton extends StatelessWidget {
  const _VerdictButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
    super.key,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Semantics(
        button: true,
        label: tooltip,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(9),
          child: Container(
            width: 44,
            height: 40,
            decoration: BoxDecoration(
              border: Border.all(color: BalanceColors.ink, width: 2),
              borderRadius: BorderRadius.circular(9),
            ),
            child: Icon(icon, size: 21),
          ),
        ),
      ),
    );
  }
}

/// Hộp thoại hỏi tên món đúng, kèm ô đồng ý gửi ảnh cho việc huấn luyện.
class CorrectionDialog extends StatefulWidget {
  const CorrectionDialog({this.initialName = '', super.key});

  final String initialName;

  @override
  State<CorrectionDialog> createState() => _CorrectionDialogState();
}

class CorrectionInput {
  const CorrectionInput({required this.dishName, required this.shareImage});

  final String dishName;
  final bool shareImage;
}

class _CorrectionDialogState extends State<CorrectionDialog> {
  late String _name = widget.initialName;
  bool _shareImage = false;

  bool get _canSubmit => _name.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Món đúng là gì?'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextFormField(
            key: const ValueKey('correction-dish-name'),
            initialValue: widget.initialName,
            autofocus: true,
            maxLength: 120,
            decoration: const InputDecoration(
              labelText: 'Tên món',
              hintText: 'Ví dụ: Bánh mì thịt',
            ),
            onChanged: (value) => setState(() => _name = value),
          ),
          CheckboxListTile(
            key: const ValueKey('correction-consent'),
            value: _shareImage,
            onChanged: (value) => setState(() => _shareImage = value ?? false),
            contentPadding: EdgeInsets.zero,
            controlAffinity: ListTileControlAffinity.leading,
            title: const Text(
              'Gửi kèm ảnh để Balance học nhận diện tốt hơn',
              style: TextStyle(fontSize: 14),
            ),
          ),
          const Text(
            'Không tích ô này thì Balance chỉ sửa tên trên máy bạn, ảnh không '
            'rời khỏi điện thoại.',
            style: TextStyle(fontSize: 12, color: BalanceColors.muted),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Hủy'),
        ),
        FilledButton(
          onPressed: _canSubmit
              ? () => Navigator.of(context).pop(
                  CorrectionInput(
                    dishName: _name.trim(),
                    shareImage: _shareImage,
                  ),
                )
              : null,
          child: const Text('Gửi'),
        ),
      ],
    );
  }
}
