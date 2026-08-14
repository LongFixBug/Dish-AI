import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:balance/features/auth/data/google_sign_in_api.dart';
import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:balance/features/journal/data/meal_api.dart';
import 'package:balance/features/journal/domain/journal_entry.dart';
import 'package:balance/features/nutrition/data/nutrition_goal_api.dart';
import 'package:balance/features/profile/domain/user_profile.dart';
import 'package:flutter/foundation.dart';

class AppState extends ChangeNotifier {
  AppState._({
    required AppStorage storage,
    required AuthGateway authGateway,
    required GoogleIdentityGateway? googleIdentityGateway,
    required NutritionGoalGateway? nutritionGoalGateway,
    required MealGateway? mealGateway,
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
         googleIdentityGateway,
         nutritionGoalGateway,
         mealGateway,
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
    this._googleIdentityGateway,
    this._nutritionGoalGateway,
    this._mealGateway,
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
    googleIdentityGateway: null,
    nutritionGoalGateway: null,
    mealGateway: null,
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
    GoogleIdentityGateway? googleIdentityGateway,
    NutritionGoalGateway? nutritionGoalGateway,
    MealGateway? mealGateway,
    StickerStore? stickerStore,
  }) async {
    // Lỗi ĐỌC (keystore bị vô hiệu khi đổi khoá màn hình, khôi phục máy mới…)
    // khác hẳn dữ liệu hỏng: coi nó là "chưa có gì" thì lần ghi kế tiếp sẽ đè
    // trắng lên payload vẫn còn giải mã được, biến sự cố tạm thời thành mất
    // dữ liệu vĩnh viễn. Để lỗi đó nổi lên cho tầng gọi xử lý.
    // Không nạp thư mục sticker ở đây: hàm này chạy cả trong unit test, nơi
    // không có platform channel để hỏi đường dẫn. main.dart lo việc đó.
    final stickers = stickerStore ?? FileStickerStore();
    final json = await storage.read();
    if (json == null) {
      return _empty(
        storage,
        authGateway,
        googleIdentityGateway,
        nutritionGoalGateway,
        mealGateway,
      ).._stickerStore = stickers;
    }
    try {
      final profileJson = json['profile'];
      final entriesJson = json['journal_entries'];
      final preferencesJson = json['preferences'];
      final accessToken = json['access_token'] as String?;
      final refreshToken = json['refresh_token'] as String?;
      final expiresRaw = json['access_token_expires_at'] as String?;
      final hasSession = accessToken != null && refreshToken != null;
      final snapshotsJson = json['account_snapshots'];
      return AppState._(
          storage: storage,
          authGateway: authGateway,
          googleIdentityGateway: googleIdentityGateway,
          nutritionGoalGateway: nutritionGoalGateway,
          mealGateway: mealGateway,
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
                      (entry) => JournalEntry.fromJson(
                        Map<String, dynamic>.from(entry),
                      ),
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
        )
        .._stickerStore = stickers
        .._loadAccountSnapshots(snapshotsJson);
    } on FormatException {
      // JSON đọc được nhưng nội dung sai định dạng → khởi động lại từ đầu là hợp lý.
      return _empty(
        storage,
        authGateway,
        googleIdentityGateway,
        nutritionGoalGateway,
        mealGateway,
      ).._stickerStore = stickers;
    } on TypeError {
      return _empty(
        storage,
        authGateway,
        googleIdentityGateway,
        nutritionGoalGateway,
        mealGateway,
      ).._stickerStore = stickers;
    }
  }

  static AppState _empty(
    AppStorage storage,
    AuthGateway authGateway,
    GoogleIdentityGateway? googleIdentityGateway,
    NutritionGoalGateway? nutritionGoalGateway,
    MealGateway? mealGateway,
  ) => AppState._(
    storage: storage,
    authGateway: authGateway,
    googleIdentityGateway: googleIdentityGateway,
    nutritionGoalGateway: nutritionGoalGateway,
    mealGateway: mealGateway,
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
  final GoogleIdentityGateway? _googleIdentityGateway;
  final NutritionGoalGateway? _nutritionGoalGateway;
  final MealGateway? _mealGateway;
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
  // email đã chuẩn hoá -> {profile, journal_entries, preferences} của lần
  // đăng xuất gần nhất. Xem _archiveAccountSnapshot.
  final Map<String, dynamic> _accountSnapshots = {};
  StickerStore _stickerStore = FileStickerStore();

  StickerStore get stickerStore => _stickerStore;

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

  Future<void> signInWithGoogle() async {
    final identityGateway = _googleIdentityGateway;
    if (identityGateway == null) {
      throw const AuthApiException('Đăng nhập Google chưa được cấu hình.');
    }
    final idToken = await identityGateway.authenticate();
    final session = await _authGateway.loginWithGoogle(idToken: idToken);
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
    await _syncNutritionGoal(profile);
  }

  Future<void> _syncNutritionGoal(UserProfile profile) async {
    final gateway = _nutritionGoalGateway;
    if (gateway == null || !_isSignedIn) return;
    try {
      final token = await validAccessToken();
      await gateway.save(profile, accessToken: token);
    } on Object {
      // The local profile remains usable when the backend is offline.
    }
  }

  Future<NutritionGoalDetails?> previewNutritionGoal() async {
    final gateway = _nutritionGoalGateway;
    final profile = _profile;
    if (profile == null || !_isSignedIn) {
      return null;
    }
    if (gateway is! NutritionGoalDetailsGateway) return null;
    final detailsGateway = gateway as NutritionGoalDetailsGateway;
    final token = await validAccessToken();
    return detailsGateway.preview(profile, accessToken: token);
  }

  /// Thêm bữa ăn, ghi kèm sticker ra file nếu có.
  ///
  /// Chỉ đường dẫn được lưu vào nhật ký; ảnh nằm riêng ngoài đĩa.
  Future<void> addJournalEntry(
    JournalEntry entry, {
    Uint8List? stickerBytes,
  }) async {
    if (_journalEntries.any((item) => item.id == entry.id)) return;
    var saved = entry;
    if (stickerBytes != null && stickerBytes.isNotEmpty) {
      final path = await _stickerStore.save(
        entryId: entry.id,
        bytes: stickerBytes,
      );
      if (path != null) saved = entry.withStickerPath(path);
    }
    _journalEntries.insert(0, saved);
    await _saveAndNotify();
  }

  /// Đồng bộ bản ghi đã lưu local lên backend; lỗi mạng không làm mất nhật ký.
  Future<bool> syncJournalEntry(
    JournalEntry entry, {
    String source = 'manual',
    String? analyzeSource,
  }) async {
    final gateway = _mealGateway;
    if (gateway == null || !_isSignedIn) return false;
    try {
      final token = await validAccessToken();
      await gateway.upsert(
        entry,
        accessToken: token,
        source: source,
        analyzeSource: analyzeSource,
      );
      return true;
    } on Object {
      return false;
    }
  }

  /// Xoá bữa ăn và trả lại bản ghi để UI có thể hiển thị thao tác hoàn tác.
  ///
  /// Bỏ bước xoá file thì thư mục tài liệu phình dần bằng ảnh mồ côi mà người
  /// dùng không có cách nào thấy hay dọn.
  Future<JournalEntry?> removeJournalEntry(
    String id, {
    bool deleteSticker = true,
  }) async {
    final removed = _journalEntries
        .where((entry) => entry.id == id)
        .toList(growable: false);
    _journalEntries.removeWhere((entry) => entry.id == id);
    if (deleteSticker) {
      for (final entry in removed) {
        await _stickerStore.delete(entry.stickerPath);
      }
    }
    await _saveAndNotify();
    return removed.isEmpty ? null : removed.first;
  }

  /// Đưa lại bản ghi vừa xoá mà không ghi đè file sticker còn giữ tạm.
  Future<void> restoreJournalEntry(JournalEntry entry) async {
    if (_journalEntries.any((item) => item.id == entry.id)) return;
    _journalEntries.insert(0, entry);
    await _saveAndNotify();
  }

  /// Dọn sticker sau khi cửa sổ hoàn tác đã đóng mà user không chọn Undo.
  Future<void> deleteJournalEntrySticker(JournalEntry entry) {
    return _stickerStore.delete(entry.stickerPath);
  }

  /// Dò lại dữ liệu nằm ngoài bộ nhớ rồi báo cho UI vẽ lại.
  ///
  /// Dùng cho thao tác kéo-xuống-tải-lại. Nhật ký vốn đã nằm sẵn trong bộ
  /// nhớ nên không cần đọc lại kho; thứ thật sự có thể đã đổi là thư mục ảnh
  /// sticker — nó nằm ngoài JSON và đường dẫn đổi sau mỗi lần cài lại app.
  Future<void> refresh() async {
    await _stickerStore.prepare();
    notifyListeners();
  }

  Future<void> updatePreferences(Set<String> values) async {
    _preferences = {...values};
    await _saveAndNotify();
  }

  Future<void> signOut() async {
    final googleIdentityGateway = _googleIdentityGateway;
    final accessToken = _accessToken;
    final refreshToken = _refreshToken;
    _archiveAccountSnapshot();
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
    // Hai việc độc lập, mỗi việc một try riêng. Gộp chung sẽ khiến Google
    // signOut ném (v7 bắt buộc initialize trước — tài khoản đăng nhập bằng mật
    // khẩu thì chưa từng initialize) nuốt luôn bước thu hồi refresh token, để
    // token sống tiếp trên máy chủ dù người dùng đã bấm đăng xuất.
    if (googleIdentityGateway != null) {
      try {
        await googleIdentityGateway.signOut();
      } on Object {
        // Phiên Google cục bộ không quan trọng bằng việc thu hồi token phía sau.
      }
    }
    if (accessToken != null && refreshToken != null) {
      try {
        await _authGateway.logout(
          accessToken: accessToken,
          refreshToken: refreshToken,
        );
      } on Object {
        // The local session is already closed; remote revocation can retry later.
      }
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
    _restoreAccountSnapshot(_accountEmail);
    await _saveAndNotify();
  }

  /// Cất hồ sơ + nhật ký của tài khoản đang đăng xuất để lần sau vào lại ngay.
  ///
  /// Đăng xuất vẫn phải dọn sạch phiên đang chạy, nhưng xoá luôn hồ sơ thì
  /// người dùng cũ đăng nhập lại bị ném về màn hình khai báo từ đầu. Bản lưu
  /// đánh theo email nên tài khoản khác đăng nhập trên cùng máy không bao giờ
  /// thấy dữ liệu của người trước.
  void _loadAccountSnapshots(Object? raw) {
    if (raw is Map) _accountSnapshots.addAll(Map<String, dynamic>.from(raw));
  }

  void _archiveAccountSnapshot() {
    final email = _accountEmail;
    final profile = _profile;
    if (email.isEmpty || profile == null) return;
    _accountSnapshots[email] = {
      'profile': profile.toJson(),
      'journal_entries': _journalEntries
          .map((entry) => entry.toJson())
          .toList(growable: false),
      'preferences': _preferences.toList(growable: false)..sort(),
    };
  }

  void _restoreAccountSnapshot(String email) {
    if (_profile != null) return;
    final snapshot = _accountSnapshots[email];
    if (snapshot is! Map) return;
    final profileJson = snapshot['profile'];
    if (profileJson is! Map) return;
    try {
      _profile = UserProfile.fromJson(Map<String, dynamic>.from(profileJson));
    } on Object {
      // Bản lưu hỏng thì coi như chưa có: người dùng khai lại còn hơn crash.
      return;
    }
    _displayName = _displayName.isEmpty ? _profile!.name : _displayName;
    final entries = snapshot['journal_entries'];
    if (entries is List) {
      _journalEntries
        ..clear()
        ..addAll(
          entries.whereType<Map>().map(
            (entry) => JournalEntry.fromJson(Map<String, dynamic>.from(entry)),
          ),
        );
    }
    final preferences = snapshot['preferences'];
    if (preferences is List) {
      _preferences = preferences.whereType<String>().toSet();
    }
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
      'account_snapshots': _accountSnapshots,
    });
    notifyListeners();
  }
}

bool _sameDate(DateTime left, DateTime right) =>
    left.year == right.year &&
    left.month == right.month &&
    left.day == right.day;
