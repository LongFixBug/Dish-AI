import 'package:balance/app.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:balance/features/auth/data/google_sign_in_api.dart';
import 'package:balance/features/nutrition/data/nutrition_goal_api.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/widgets.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const secureStorage = FlutterSecureStorage();
  runApp(BalanceApp(appState: await _restoreState(SecureAppStorage(secureStorage))));
}

Future<AppState> _restoreState(AppStorage storage) async {
  try {
    return await AppState.restore(
      storage,
      authGateway: AuthApi(),
      googleIdentityGateway: GoogleSignInGateway(),
      nutritionGoalGateway: NutritionGoalApi(),
    );
  } on Object {
    // Không đọc được kho bảo mật (keystore bị vô hiệu sau khi đổi khoá màn
    // hình, khôi phục sang máy mới…). Chạy tạm trên bộ nhớ để KHÔNG ghi đè lên
    // dữ liệu cũ: nó vẫn còn nguyên và mở lại được ở lần khởi động sau.
    return AppState.restore(
      MemoryAppStorage(),
      authGateway: AuthApi(),
      googleIdentityGateway: GoogleSignInGateway(),
      nutritionGoalGateway: NutritionGoalApi(),
    );
  }
}
