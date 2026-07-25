import 'package:balance/app.dart';
import 'package:balance/core/state/app_state.dart';
import 'package:balance/core/storage/app_storage.dart';
import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final preferences = await SharedPreferences.getInstance();
  final state = await AppState.restore(
    SharedPreferencesAppStorage(preferences),
  );
  runApp(BalanceApp(appState: state));
}
