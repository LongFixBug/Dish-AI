import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class AppStorage {
  Future<Map<String, dynamic>?> read();

  Future<void> write(Map<String, dynamic> value);
}

class SecureAppStorage implements AppStorage {
  SecureAppStorage(this._storage);

  static const _key = 'balance.app_state.v2';
  final FlutterSecureStorage _storage;

  @override
  Future<Map<String, dynamic>?> read() async {
    final raw = await _storage.read(key: _key);
    if (raw == null || raw.isEmpty) return null;
    final decoded = jsonDecode(raw);
    return decoded is Map<String, dynamic> ? decoded : null;
  }

  @override
  Future<void> write(Map<String, dynamic> value) async {
    await _storage.write(key: _key, value: jsonEncode(value));
  }
}

class MemoryAppStorage implements AppStorage {
  Map<String, dynamic>? _value;

  @override
  Future<Map<String, dynamic>?> read() async {
    final value = _value;
    return value == null
        ? null
        : Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
  }

  @override
  Future<void> write(Map<String, dynamic> value) async {
    _value = Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
  }
}
