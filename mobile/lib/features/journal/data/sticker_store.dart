import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

/// Nơi cất ảnh sticker của từng bữa ăn.
abstract interface class StickerStore {
  /// Nạp sẵn thư mục sticker để [StickerPaths] dùng được ngay.
  ///
  /// Phải gọi lúc khởi động: widget dựng đồng bộ nên không thể tự đi hỏi
  /// thư mục tài liệu, mà nếu chưa ai chạm vào kho thì đường dẫn còn rỗng và
  /// mọi sticker biến mất khỏi màn hình.
  Future<void> prepare();

  /// Trả về TÊN FILE (không phải đường dẫn tuyệt đối) — xem [StickerPaths].
  Future<String?> save({required String entryId, required Uint8List bytes});

  Future<Uint8List?> read(String? name);

  Future<void> delete(String? name);
}

/// Ghép tên file sticker với thư mục tài liệu hiện tại.
///
/// Nhật ký KHÔNG được lưu đường dẫn tuyệt đối: trên iOS, đường dẫn thư mục
/// tài liệu chứa một UUID container đổi mỗi lần cài lại hoặc khôi phục máy,
/// trong khi nhật ký nằm ở Keychain nên sống sót. Lưu đường dẫn tuyệt đối là
/// sau một lần cài lại, mọi sticker trỏ vào chỗ không còn tồn tại.
class StickerPaths {
  StickerPaths._();

  /// Thư mục sticker của lần chạy hiện tại; [FileStickerStore] đặt giá trị.
  static String? directory;

  /// File sticker nếu còn tồn tại, ``null`` nếu không.
  ///
  /// Nhận cả đường dẫn tuyệt đối kiểu cũ: chỉ lấy phần tên file nên dữ liệu
  /// lưu từ bản trước tự khớp lại mà không cần bước migrate riêng.
  static File? fileFor(String? name) {
    final dir = directory;
    if (dir == null || name == null || name.isEmpty) return null;
    final baseName = name.split('/').last;
    if (baseName.isEmpty) return null;
    final file = File('$dir/$baseName');
    return file.existsSync() ? file : null;
  }
}

/// Lưu sticker thành file PNG trong thư mục tài liệu của app.
///
/// Ảnh KHÔNG được nhét vào bản JSON của nhật ký: cả nhật ký nằm chung một
/// chuỗi trong secure storage, thêm vài chục ảnh base64 vào đó là mỗi lần ghi
/// bất kỳ thứ gì cũng phải mã hoá lại toàn bộ. File riêng + JSON giữ đường
/// dẫn thì ghi nhật ký vẫn nhẹ như cũ.
class FileStickerStore implements StickerStore {
  FileStickerStore({Directory? rootDirectory}) : _root = rootDirectory;

  static const folderName = 'stickers';

  Directory? _root;

  Future<Directory> _directory() async {
    final cached = _root;
    if (cached != null) {
      if (!cached.existsSync()) await cached.create(recursive: true);
      StickerPaths.directory = cached.path;
      return cached;
    }
    final documents = await getApplicationDocumentsDirectory();
    final directory = Directory('${documents.path}/$folderName');
    if (!directory.existsSync()) await directory.create(recursive: true);
    StickerPaths.directory = directory.path;
    return _root = directory;
  }

  /// Đổi id bữa ăn thành tên file an toàn.
  ///
  /// Id được ghép từ tên món nên mang cả dấu tiếng Việt lẫn dấu gạch chéo;
  /// thả thẳng vào đường dẫn là mở cửa cho việc ghi ra ngoài thư mục.
  static String fileNameFor(String entryId) {
    // Dấu chấm bị loại luôn: giữ lại thì "..": vẫn nằm trong tên file và ai
    // đọc đường dẫn cũng phải dừng lại tự hỏi nó có thoát thư mục được không.
    final safe = entryId.replaceAll(RegExp(r'[^A-Za-z0-9_-]'), '_');
    final trimmed = safe.replaceAll(RegExp(r'^[_-]+'), '');
    final name = trimmed.isEmpty ? 'sticker' : trimmed;
    return '${name.length > 80 ? name.substring(0, 80) : name}.png';
  }

  @override
  Future<void> prepare() async {
    try {
      await _directory();
    } on Object {
      // Không lấy được thư mục thì app vẫn chạy, chỉ là không hiện sticker.
    }
  }

  @override
  Future<String?> save({
    required String entryId,
    required Uint8List bytes,
  }) async {
    if (bytes.isEmpty) return null;
    try {
      final directory = await _directory();
      final name = fileNameFor(entryId);
      await File('${directory.path}/$name').writeAsBytes(bytes, flush: true);
      return name;
    } on Object {
      // Hết dung lượng hay không ghi được: bữa ăn vẫn phải lưu được, chỉ là
      // không có sticker.
      return null;
    }
  }

  @override
  Future<Uint8List?> read(String? name) async {
    if (name == null || name.isEmpty) return null;
    try {
      final file = File('${(await _directory()).path}/${name.split('/').last}');
      if (!file.existsSync()) return null;
      return await file.readAsBytes();
    } on Object {
      return null;
    }
  }

  @override
  Future<void> delete(String? name) async {
    if (name == null || name.isEmpty) return;
    try {
      final file = File('${(await _directory()).path}/${name.split('/').last}');
      if (file.existsSync()) await file.delete();
    } on Object {
      // File rác còn lại không đáng để chặn việc xoá bữa ăn.
    }
  }
}
