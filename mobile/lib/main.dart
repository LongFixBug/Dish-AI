import 'package:balance/app.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:balance/features/auth/data/auth_api.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/widgets.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  const secureStorage = FlutterSecureStorage();
  final state = await AppState.restore(
    SecureAppStorage(secureStorage),
    authGateway: AuthApi(),
  );
  runApp(BalanceApp(appState: state));
}
