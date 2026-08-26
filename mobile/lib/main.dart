import 'package:flutter/material.dart';
import 'src/api/gaon_api.dart';
import 'src/screens/login_screen.dart';
import 'src/screens/market_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const GaonOneApp());
}

class GaonOneApp extends StatefulWidget {
  const GaonOneApp({super.key});
  @override
  State<GaonOneApp> createState() => _GaonOneAppState();
}

class _GaonOneAppState extends State<GaonOneApp> {
  bool? _loggedIn;
  @override
  void initState() {
    super.initState();
    GaonApi.hasToken().then((value) => setState(() => _loggedIn = value));
  }
  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF1F7A45));
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'GaonOne',
      theme: ThemeData(colorScheme: scheme, useMaterial3: true, scaffoldBackgroundColor: const Color(0xFFF6F8F4)),
      home: _loggedIn == null
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _loggedIn!
              ? const MarketScreen()
              : LoginScreen(onLoggedIn: () => setState(() => _loggedIn = true)),
    );
  }
}
