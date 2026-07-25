import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  AppState._({
    required AppStorage storage,
    required bool isSignedIn,
    required String accountEmail,
    required String displayName,
    required UserProfile? profile,
    required List<JournalEntry> journalEntries,
    required Set<String> preferences,
  }) : this._values(
         storage,
         isSignedIn,
         accountEmail,
         displayName,
         profile,
         journalEntries,
         preferences,
       );

  AppState._values(
    this._storage,
    this._isSignedIn,
    this._accountEmail,
    this._displayName,
    this._profile,
    this._journalEntries,
    this._preferences,
  );

  factory AppState.memory() => AppState._(
    storage: MemoryAppStorage(),
    isSignedIn: false,
    accountEmail: '',
    displayName: '',
    profile: null,
    journalEntries: [],
    preferences: {...defaultPreferences},
  );

  static const defaultPreferences = {'Nhiều đạm', 'Ít dầu', 'Món Việt'};

  static Future<AppState> restore(AppStorage storage) async {
    try {
      final json = await storage.read();
      if (json == null) {
        return AppState._(
          storage: storage,
          isSignedIn: false,
          accountEmail: '',
          displayName: '',
          profile: null,
          journalEntries: [],
          preferences: {...defaultPreferences},
        );
      }
      final profileJson = json['profile'];
      final entriesJson = json['journal_entries'];
      final preferencesJson = json['preferences'];
      return AppState._(
        storage: storage,
        isSignedIn: json['is_signed_in'] as bool? ?? false,
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
      );
    } on Object {
      return AppState._(
        storage: storage,
        isSignedIn: false,
        accountEmail: '',
        displayName: '',
        profile: null,
        journalEntries: [],
        preferences: {...defaultPreferences},
      );
    }
  }

  final AppStorage _storage;
  bool _isSignedIn;
  String _accountEmail;
  String _displayName;
  UserProfile? _profile;
  final List<JournalEntry> _journalEntries;
  Set<String> _preferences;

  bool get isSignedIn => _isSignedIn;
  String get accountEmail => _accountEmail;
  String get displayName => _displayName;
  UserProfile? get profile => _profile;
  List<JournalEntry> get journalEntries => List.unmodifiable(_journalEntries);
  Set<String> get preferences => Set.unmodifiable(_preferences);

  Future<void> signIn({required String email, String displayName = ''}) async {
    _accountEmail = email.trim().toLowerCase();
    if (displayName.trim().isNotEmpty) _displayName = displayName.trim();
    _isSignedIn = true;
    await _saveAndNotify();
  }

  Future<void> completeProfile(UserProfile profile) async {
    _profile = profile;
    _accountEmail = profile.email.trim().toLowerCase();
    _displayName = profile.name;
    _isSignedIn = true;
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
    _isSignedIn = false;
    await _saveAndNotify();
  }

  List<JournalEntry> entriesForDate(DateTime date) {
    return _journalEntries
        .where((entry) => _sameDate(entry.loggedAt, date))
        .toList(growable: false);
  }

  double todayCalories(DateTime date) {
    return entriesForDate(
      date,
    ).fold(0, (total, entry) => total + entry.calories);
  }

  Future<void> _saveAndNotify() async {
    await _storage.write({
      'is_signed_in': _isSignedIn,
      'account_email': _accountEmail,
      'display_name': _displayName,
      'profile': _profile?.toJson(),
      'journal_entries': _journalEntries
          .map((entry) => entry.toJson())
          .toList(growable: false),
      'preferences': _preferences.toList(growable: false)..sort(),
    });
    notifyListeners();
  }
}

bool _sameDate(DateTime left, DateTime right) {
  return left.year == right.year &&
      left.month == right.month &&
      left.day == right.day;
}
