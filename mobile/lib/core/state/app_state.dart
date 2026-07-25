import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  AppState._({
    required AppStorage storage,
    required AuthGateway authGateway,
    required bool isSignedIn,
    required String accountEmail,
    required String displayName,
    required UserProfile? profile,
    required List<JournalEntry> journalEntries,
    required Set<String> preferences,
    required String? accessToken,
    required String? refreshToken,
    required DateTime? accessTokenExpiresAt,
  }) : this._values(
         storage,
         authGateway,
         isSignedIn,
         accountEmail,
         displayName,
         profile,
         journalEntries,
         preferences,
         accessToken,
         refreshToken,
         accessTokenExpiresAt,
       );

  AppState._values(
    this._storage,
    this._authGateway,
    this._isSignedIn,
    this._accountEmail,
    this._displayName,
    this._profile,
    this._journalEntries,
    this._preferences,
    this._accessToken,
    this._refreshToken,
    this._accessTokenExpiresAt,
  );

  factory AppState.memory() => AppState._(
    storage: MemoryAppStorage(),
    authGateway: const UnavailableAuthGateway(),
    isSignedIn: false,
    accountEmail: '',
    displayName: '',
    profile: null,
    journalEntries: [],
    preferences: {...defaultPreferences},
    accessToken: null,
    refreshToken: null,
    accessTokenExpiresAt: null,
  );

  static const defaultPreferences = {'Nhiều đạm', 'Ít dầu', 'Món Việt'};

  static Future<AppState> restore(
    AppStorage storage, {
    AuthGateway authGateway = const UnavailableAuthGateway(),
  }) async {
    try {
      final json = await storage.read();
      if (json == null) return _empty(storage, authGateway);
      final profileJson = json['profile'];
      final entriesJson = json['journal_entries'];
      final preferencesJson = json['preferences'];
      final accessToken = json['access_token'] as String?;
      final refreshToken = json['refresh_token'] as String?;
      final expiresRaw = json['access_token_expires_at'] as String?;
      final hasSession = accessToken != null && refreshToken != null;
      return AppState._(
        storage: storage,
        authGateway: authGateway,
        isSignedIn: hasSession,
        accountEmail: json['account_email'] as String? ?? '',
        displayName: json['display_name'] as String? ?? '',
        profile: profileJson is Map
            ? UserProfile.fromJson(Map<String, dynamic>.from(profileJson))
            : null,
        journalEntries: entriesJson is List
            ? entriesJson
                  .whereType<Map>()
                  .map(
                    (entry) =>
                        JournalEntry.fromJson(Map<String, dynamic>.from(entry)),
                  )
                  .toList()
            : [],
        preferences: preferencesJson is List
            ? preferencesJson.whereType<String>().toSet()
            : {...defaultPreferences},
        accessToken: accessToken,
        refreshToken: refreshToken,
        accessTokenExpiresAt: expiresRaw == null
            ? null
            : DateTime.tryParse(expiresRaw)?.toUtc(),
      );
    } on Object {
      return _empty(storage, authGateway);
    }
  }

  static AppState _empty(AppStorage storage, AuthGateway authGateway) =>
      AppState._(
        storage: storage,
        authGateway: authGateway,
        isSignedIn: false,
        accountEmail: '',
        displayName: '',
        profile: null,
        journalEntries: [],
        preferences: {...defaultPreferences},
        accessToken: null,
        refreshToken: null,
        accessTokenExpiresAt: null,
      );

  final AppStorage _storage;
  final AuthGateway _authGateway;
  bool _isSignedIn;
  String _accountEmail;
  String _displayName;
  UserProfile? _profile;
  final List<JournalEntry> _journalEntries;
  Set<String> _preferences;
  String? _accessToken;
  String? _refreshToken;
  DateTime? _accessTokenExpiresAt;
  Future<AuthSession>? _refreshInFlight;

  bool get isSignedIn => _isSignedIn;
  String get accountEmail => _accountEmail;
  String get displayName => _displayName;
  UserProfile? get profile => _profile;
  String? get accessToken => _accessToken;
  List<JournalEntry> get journalEntries => List.unmodifiable(_journalEntries);
  Set<String> get preferences => Set.unmodifiable(_preferences);

  Future<void> signIn({required String email, required String password}) async {
    final normalizedEmail = email.trim().toLowerCase();
    final session = await _authGateway.login(
      email: normalizedEmail,
      password: password,
    );
    await _applySession(session);
  }

  Future<void> signUp({
    required String email,
    required String password,
    required String displayName,
  }) async {
    final session = await _authGateway.register(
      email: email.trim().toLowerCase(),
      password: password,
      displayName: displayName.trim(),
    );
    await _applySession(session);
  }

  Future<String> validAccessToken() async {
    final accessToken = _accessToken;
    final refreshToken = _refreshToken;
    if (accessToken == null || refreshToken == null) {
      throw const AuthApiException('Phiên đăng nhập đã kết thúc.');
    }
    final expiresAt = _accessTokenExpiresAt;
    final shouldRefresh =
        expiresAt == null ||
        expiresAt.isBefore(
          DateTime.now().toUtc().add(const Duration(seconds: 30)),
        );
    if (!shouldRefresh) return accessToken;

    final refreshFuture = _refreshInFlight ??= _refreshSession(refreshToken);
    final session = await refreshFuture;
    return session.accessToken;
  }

  Future<void> completeProfile(UserProfile profile) async {
    _profile = profile;
    _accountEmail = profile.email.trim().toLowerCase();
    _displayName = profile.name;
    await _saveAndNotify();
  }

  Future<void> addJournalEntry(JournalEntry entry) async {
    if (_journalEntries.any((item) => item.id == entry.id)) return;
    _journalEntries.insert(0, entry);
    await _saveAndNotify();
  }

  Future<void> removeJournalEntry(String id) async {
    _journalEntries.removeWhere((entry) => entry.id == id);
    await _saveAndNotify();
  }

  Future<void> updatePreferences(Set<String> values) async {
    _preferences = {...values};
    await _saveAndNotify();
  }

  Future<void> signOut() async {
    final accessToken = _accessToken;
    final refreshToken = _refreshToken;
    _isSignedIn = false;
    _accessToken = null;
    _refreshToken = null;
    _accessTokenExpiresAt = null;
    _accountEmail = '';
    _displayName = '';
    _profile = null;
    _journalEntries.clear();
    _preferences = {...defaultPreferences};
    await _saveAndNotify();
    try {
      if (accessToken != null && refreshToken != null) {
        await _authGateway.logout(
          accessToken: accessToken,
          refreshToken: refreshToken,
        );
      }
    } on Object {
      // The local session is already closed; remote revocation can retry later.
    }
  }

  List<JournalEntry> entriesForDate(DateTime date) => _journalEntries
      .where((entry) => _sameDate(entry.loggedAt, date))
      .toList(growable: false);

  double todayCalories(DateTime date) =>
      entriesForDate(date).fold(0, (total, entry) => total + entry.calories);

  Future<void> _applySession(AuthSession session) async {
    _accessToken = session.accessToken;
    _refreshToken = session.refreshToken;
    _accessTokenExpiresAt = session.expiresAt;
    _accountEmail = session.user.email.trim().toLowerCase();
    _displayName = session.user.displayName.trim();
    _isSignedIn = true;
    await _saveAndNotify();
  }

  Future<AuthSession> _refreshSession(String refreshToken) async {
    try {
      final session = await _authGateway.refresh(refreshToken);
      if (!_isSignedIn || _refreshToken != refreshToken) {
        throw const AuthApiException('Phiên đăng nhập đã kết thúc.');
      }
      await _applySession(session);
      return session;
    } finally {
      _refreshInFlight = null;
    }
  }

  Future<void> _saveAndNotify() async {
    await _storage.write({
      'account_email': _accountEmail,
      'display_name': _displayName,
      'access_token': _accessToken,
      'refresh_token': _refreshToken,
      'access_token_expires_at': _accessTokenExpiresAt?.toIso8601String(),
      'profile': _profile?.toJson(),
      'journal_entries': _journalEntries
          .map((entry) => entry.toJson())
          .toList(growable: false),
      'preferences': _preferences.toList(growable: false)..sort(),
    });
    notifyListeners();
  }
}

bool _sameDate(DateTime left, DateTime right) =>
    left.year == right.year &&
    left.month == right.month &&
    left.day == right.day;
