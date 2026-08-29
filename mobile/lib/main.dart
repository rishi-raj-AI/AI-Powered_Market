import 'package:flutter/material.dart';
import 'src/api/gaon_api.dart';
import 'src/screens/login_screen.dart';
import 'src/screens/customer_shell.dart';
import 'src/screens/merchant_workspace.dart' as merchant;
import 'src/screens/role_workspaces.dart';

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
  bool loading = true;
  bool loggedIn = false;
  String role = 'customer';

  @override
  void initState() {
    super.initState();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      if (await GaonApi.hasToken()) {
        final me = await GaonApi.me();
        if (!mounted) return;
        setState(() { loggedIn = true; role = me.role; loading = false; });
      } else if (mounted) {
        setState(() => loading = false);
      }
    } catch (_) {
      await GaonApi.logout();
      if (mounted) setState(() { loggedIn = false; loading = false; });
    }
  }

  Future<void> _onLoggedIn() async {
    setState(() => loading = true);
    await _bootstrap();
  }

  Future<void> _logout() async {
    await GaonApi.logout();
    if (mounted) setState(() { loggedIn = false; role = 'customer'; loading = false; });
  }

  Widget _home() {
    if (!loggedIn) return LoginScreen(onLoggedIn: _onLoggedIn);
    return switch (role) {
      'merchant' => merchant.MerchantWorkspace(onLogout: _logout),
      'delivery' => DeliveryWorkspace(onLogout: _logout),
      'admin' => AdminWorkspace(onLogout: _logout),
      _ => CustomerShell(onLogout: _logout),
    };
  }

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFF1F7A45));
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'GaonOne',
      theme: ThemeData(
        colorScheme: scheme,
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF6F8F4),
        inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder()),
      ),
      home: loading ? const Scaffold(body: Center(child: CircularProgressIndicator())) : _home(),
    );
  }
}
