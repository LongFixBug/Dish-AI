import 'package:flutter/services.dart';

/// Golden test chạy trong test bundle nên cần nạp rõ cả font chữ và icon.
/// Nếu chỉ nạp Baloo, Material icons bị vẽ thành ô vuông; ảnh golden khi đó
/// không đại diện cho giao diện thật trên simulator.
Future<void> loadBalanceTestFonts() async {
  final baloo = FontLoader('Baloo 2')
    ..addFont(rootBundle.load('assets/fonts/Baloo2-Variable.ttf'));
  final materialIcons = FontLoader('MaterialIcons')
    ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));

  await Future.wait([baloo.load(), materialIcons.load()]);
}
