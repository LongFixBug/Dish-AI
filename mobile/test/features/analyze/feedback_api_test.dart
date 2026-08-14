import 'dart:convert';
import 'dart:typed_data';

import 'package:balance/features/analyze/data/feedback_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

void main() {
  test('sends camera provenance and recognition event with consent', () async {
    late http.MultipartRequest request;
    final api = FeedbackApi(
      client: _RecordingClient((captured) async {
        request = captured as http.MultipartRequest;
        return _response({});
      }),
      baseUrl: Uri.parse('http://localhost:8000'),
    );

    await api.submitCorrection(
      imageBytes: Uint8List.fromList([1, 2, 3]),
      filename: 'camera.jpg',
      correctDishName: 'Phở bò',
      consentToTraining: true,
      accessToken: 'token',
      recognitionEventId: 'event-1',
      captureSource: 'camera',
    );

    expect(request.fields['consent_to_training'], 'true');
    expect(request.fields['recognition_event_id'], 'event-1');
    expect(request.fields['capture_source'], 'camera');
    expect(request.files.single.filename, 'camera.jpg');
  });
}

class _RecordingClient extends http.BaseClient {
  _RecordingClient(this.handler);

  final Future<http.StreamedResponse> Function(http.BaseRequest request) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) => handler(request);
}

http.StreamedResponse _response(Map<String, Object?> body) {
  return http.StreamedResponse(
    Stream.value(utf8.encode(jsonEncode(body))),
    200,
    headers: {'content-type': 'application/json'},
  );
}
