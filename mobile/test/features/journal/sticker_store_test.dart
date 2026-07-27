import 'dart:io';
import 'dart:typed_data';

import 'package:balance/features/journal/data/sticker_store.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late Directory root;
  late FileStickerStore store;

  setUp(() async {
    root = await Directory.systemTemp.createTemp('sticker-store-test');
    store = FileStickerStore(rootDirectory: root);
  });

  tearDown(() async {
    if (root.existsSync()) await root.delete(recursive: true);
  });

  test('lưu sticker rồi đọc lại đúng nội dung', () async {
    final bytes = Uint8List.fromList([1, 2, 3, 4, 5]);

    final name = await store.save(entryId: 'entry-1', bytes: bytes);

    expect(name, isNotNull);
    expect(await store.read(name!), bytes);
  });

  test('trả về TÊN FILE chứ không phải đường dẫn tuyệt đối', () async {
    // Đường dẫn thư mục tài liệu trên iOS chứa UUID container, đổi mỗi lần
    // cài lại app — lưu nguyên đường dẫn là sticker mất hết sau một lần cài.
    final name = await store.save(
      entryId: 'entry-1',
      bytes: Uint8List.fromList([1]),
    );

    expect(name, isNot(contains('/')));
    expect(File('${root.path}/$name').existsSync(), isTrue);
  });

  test('StickerPaths ghép tên với thư mục hiện tại, chịu cả path kiểu cũ', () async {
    final name = await store.save(
      entryId: 'entry-1',
      bytes: Uint8List.fromList([1]),
    );
    StickerPaths.directory = root.path;

    expect(StickerPaths.fileFor(name)?.existsSync(), isTrue);
    // Dữ liệu cũ lưu đường dẫn tuyệt đối của container đã biến mất: vẫn khớp
    // lại được vì chỉ phần tên file được dùng.
    expect(
      StickerPaths.fileFor('/khong/con/ton/tai/$name')?.existsSync(),
      isTrue,
    );
    expect(StickerPaths.fileFor('khong-co-that.png'), isNull);
    expect(StickerPaths.fileFor(null), isNull);
  });

  test('tên file bám theo id bữa ăn nên không đụng nhau', () async {
    final first = await store.save(
      entryId: 'entry-1',
      bytes: Uint8List.fromList([1]),
    );
    final second = await store.save(
      entryId: 'entry-2',
      bytes: Uint8List.fromList([2]),
    );

    expect(first, isNot(second));
    expect(await store.read(first!), Uint8List.fromList([1]));
    expect(await store.read(second!), Uint8List.fromList([2]));
  });

  test('id có ký tự lạ vẫn ra tên file an toàn', () async {
    // id sinh từ tên món nên có dấu, khoảng trắng, dấu gạch — không được để
    // chúng lọt thẳng vào tên file rồi đẻ ra đường dẫn ngoài thư mục.
    final path = await store.save(
      entryId: '123-Bánh mì kẹp thịt/../../escape',
      bytes: Uint8List.fromList([9]),
    );

    expect(path, isNotNull);
    expect(path, isNot(contains('..')));
    expect(File('${root.path}/$path').parent.path, root.path);
  });

  test('lưu bytes rỗng thì không tạo file', () async {
    expect(await store.save(entryId: 'e', bytes: Uint8List(0)), isNull);
  });

  test('xoá sticker thì file biến mất', () async {
    final name = await store.save(
      entryId: 'entry-1',
      bytes: Uint8List.fromList([7]),
    );
    expect(File('${root.path}/$name').existsSync(), isTrue);

    await store.delete(name);

    expect(File('${root.path}/$name').existsSync(), isFalse);
  });

  test('xoá file không tồn tại không được ném lỗi', () async {
    // Bữa ăn cũ chưa có sticker, hoặc file đã bị dọn trước đó: xoá nhật ký
    // vẫn phải chạy trót lọt.
    await store.delete('${root.path}/khong-co-that.png');
    await store.delete(null);
  });

  test('đọc file không tồn tại trả null thay vì ném', () async {
    expect(await store.read('${root.path}/thieu.png'), isNull);
    expect(await store.read(null), isNull);
  });
}
