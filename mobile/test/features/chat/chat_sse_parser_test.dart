import 'package:balance/features/chat/data/chat_api.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('assembles an SSE JSON payload split across chunks', () {
    final decoder = ChatSseDecoder();

    expect(decoder.addText('event: delta\ndata: {"text":"bún'), isEmpty);
    final events = decoder.addText(' bò"}\n\n');

    expect(events.single.name, 'delta');
    expect(events.single.data['text'], 'bún bò');
  });

  test('joins multiple data lines and flushes the final event', () {
    final decoder = ChatSseDecoder();

    decoder.addText('event: error\r\ndata: {"message":"mất');
    final events = decoder.addText(' mạng"}\r\n');

    expect(events, isEmpty);
    final flushed = decoder.finish();
    expect(flushed.single.name, 'error');
    expect(flushed.single.data['message'], 'mất mạng');
  });
}
