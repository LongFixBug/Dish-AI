import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

abstract interface class AppStorage {
  Future<Map<String, dynamic>?> read();

  Future<void> write(Map<String, dynamic> value);
}

class SharedPreferencesAppStorage implements AppStorage {
  SharedPreferencesAppStorage(this._preferences);

  static const _key = 'balance.app_state.v1';
  final SharedPreferences _preferences;

  @override
  Future<Map<String, dynamic>?> read() async {
    final raw = _preferences.getString(_key);
    if (raw == null || raw.isEmpty) return null;
    final decoded = jsonDecode(raw);
    return decoded is Map<String, dynamic> ? decoded : null;
  }

  @override
  Future<void> write(Map<String, dynamic> value) async {
    final saved = await _preferences.setString(_key, jsonEncode(value));
    if (!saved) throw StateError('Không thể lưu dữ liệu ứng dụng');
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
