import 'dart:convert';
import 'dart:typed_data';

import 'package:balance/features/analyze/data/analyze_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

void main() {
  test(
    'uploads the selected image to the FastAPI multipart endpoint',
    () async {
      late http.MultipartRequest capturedRequest;
      final client = _RecordingClient((request) async {
        capturedRequest = request as http.MultipartRequest;
        return _jsonResponse({
          'dish_name': 'Cơm tấm',
          'source': 'vision',
          'dishes': <Object>[],
        });
      });
      final api = AnalyzeApi(
        client: client,
        baseUrl: Uri.parse('http://10.0.2.2:8000'),
      );

      final result = await api.analyzeImage(
        bytes: Uint8List.fromList([0xff, 0xd8, 0xff]),
        filename: 'com-tam.jpg',
      );

      expect(capturedRequest.method, 'POST');
      expect(
        capturedRequest.url.toString(),
        'http://10.0.2.2:8000/api/v1/analyze',
      );
      expect(capturedRequest.files.single.field, 'file');
      expect(capturedRequest.files.single.filename, 'com-tam.jpg');
      expect(capturedRequest.files.single.contentType.toString(), 'image/jpeg');
      expect(result.dishName, 'Cơm tấm');
    },
  );

  test(
    'turns FastAPI validation responses into a friendly exception',
    () async {
      final api = AnalyzeApi(
        client: _RecordingClient(
          (_) async => _jsonResponse({
            'detail': 'Chỉ chấp nhận file ảnh',
          }, statusCode: 422),
        ),
        baseUrl: Uri.parse('http://localhost:8000'),
      );

      expect(
        () => api.analyzeImage(
          bytes: Uint8List.fromList([1, 2, 3]),
          filename: 'notes.txt',
        ),
        throwsA(
          isA<AnalyzeApiException>().having(
            (error) => error.message,
            'message',
            contains('Chỉ chấp nhận file ảnh'),
          ),
        ),
      );
    },
  );

  test(
    'treats a 200 response carrying an analysis error as a failure',
    () async {
      final api = AnalyzeApi(
        client: _RecordingClient(
          (_) async => _jsonResponse({
            'source': 'vision',
            'dishes': <Object>[],
            'error': 'Vision cloud offline',
          }),
        ),
        baseUrl: Uri.parse('http://localhost:8000'),
      );

      expect(
        () => api.analyzeImage(
          bytes: Uint8List.fromList([0xff, 0xd8]),
          filename: 'food.jpg',
        ),
        throwsA(
          isA<AnalyzeApiException>().having(
            (error) => error.message,
            'message',
            contains('Vision cloud offline'),
          ),
        ),
      );
    },
  );

  test(
    'rejects empty and unsupported images before opening a request',
    () async {
      var requestCount = 0;
      final api = AnalyzeApi(
        client: _RecordingClient((_) async {
          requestCount += 1;
          return _jsonResponse({'source': 'vision', 'dishes': <Object>[]});
        }),
        baseUrl: Uri.parse('http://localhost:8000'),
      );

      await expectLater(
        () => api.analyzeImage(bytes: Uint8List(0), filename: 'empty.jpg'),
        throwsA(isA<AnalyzeApiException>()),
      );
      await expectLater(
        () => api.analyzeImage(
          bytes: Uint8List.fromList([1, 2, 3]),
          filename: 'photo.heic',
        ),
        throwsA(
          isA<AnalyzeApiException>().having(
            (error) => error.message,
            'message',
            contains('HEIC'),
          ),
        ),
      );
      expect(requestCount, 0);
    },
  );

  test('keeps the HTTP status when an error body is not JSON', () async {
    final api = AnalyzeApi(
      client: _RecordingClient(
        (_) async => http.StreamedResponse(
          Stream.value(utf8.encode('service unavailable')),
          503,
        ),
      ),
      baseUrl: Uri.parse('http://localhost:8000'),
    );

    await expectLater(
      () => api.analyzeImage(
        bytes: Uint8List.fromList([0xff, 0xd8, 0xff]),
        filename: 'food.jpg',
      ),
      throwsA(
        isA<AnalyzeApiException>().having(
          (error) => error.message,
          'message',
          contains('HTTP 503'),
        ),
      ),
    );
  });
}

class _RecordingClient extends http.BaseClient {
  _RecordingClient(this.handler);

  final Future<http.StreamedResponse> Function(http.BaseRequest request)
  handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) =>
      handler(request);
}

http.StreamedResponse _jsonResponse(
  Map<String, Object?> body, {
  int statusCode = 200,
}) {
  final bytes = utf8.encode(jsonEncode(body));
  return http.StreamedResponse(
    Stream.value(bytes),
    statusCode,
    headers: {'content-type': 'application/json; charset=utf-8'},
  );
}
