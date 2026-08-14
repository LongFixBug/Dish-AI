import 'dart:convert';

import 'package:balance/features/rag/data/rag_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('sends an authenticated question to the RAG endpoint', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/api/v1/rag/chat');
      expect(request.headers['authorization'], 'Bearer access-token');
      expect(jsonDecode(request.body), {'question': 'Phở bò có gì?'});
      return http.Response.bytes(
        utf8.encode(
          jsonEncode({
            'answer': 'Phở bò có bánh phở.',
            'sources': [
              {
                'document_id': 'pho-bo',
                'title': 'Phở bò',
                'source': 'foodai_demo',
                'score': 0.7344,
              },
            ],
          }),
        ),
        200,
      );
    });
    final api = RagApi(client: client, baseUrl: Uri.parse('http://api.test'));

    final result = await api.ask(
      question: '  Phở bò có gì?  ',
      accessToken: 'access-token',
    );

    expect(result.answer, 'Phở bò có bánh phở.');
    expect(result.sources.single.documentId, 'pho-bo');
    expect(result.sources.single.title, 'Phở bò');
    expect(result.sources.single.source, 'foodai_demo');
    expect(result.sources.single.score, 0.7344);
  });

  test('shows the backend error without losing its friendly message', () async {
    final api = RagApi(
      client: MockClient(
        (_) async => http.Response.bytes(
          utf8.encode(
            jsonEncode({
              'detail': 'RAG hiện chưa sẵn sàng. Vui lòng thử lại sau.',
            }),
          ),
          503,
        ),
      ),
      baseUrl: Uri.parse('http://api.test'),
    );

    await expectLater(
      () => api.ask(question: 'Phở bò có gì?', accessToken: 'access-token'),
      throwsA(
        isA<RagApiException>().having(
          (error) => error.message,
          'message',
          'RAG hiện chưa sẵn sàng. Vui lòng thử lại sau.',
        ),
      ),
    );
  });
}
