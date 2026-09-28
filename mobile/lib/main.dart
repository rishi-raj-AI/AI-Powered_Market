import 'package:flutter/material.dart';
import 'src/api/gaon_api.dart';
import 'src/auth/firebase_google_sign_in.dart';
import 'src/screens/login_screen.dart';
import 'src/screens/customer_shell.dart';
import 'src/screens/role_workspaces.dart';
import 'src/theme/gaon_theme.dart';

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
  bool bootstrapUnavailable = false;

  final GlobalKey<ScaffoldMessengerState> _messengerKey = GlobalKey<ScaffoldMessengerState>();

  @override
  void initState() {
    super.initState();
    GaonApi.onSessionExpired = _onSessionExpired;
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    try {
      if (await GaonApi.hasToken()) {
        final me = await GaonApi.me();
        if (!mounted) return;
        setState(() { loggedIn = true; role = me.role; loading = false; bootstrapUnavailable = false; });
      } else if (mounted) {
        setState(() => loading = false);
      }
    } on SessionExpired {
      if (mounted) setState(() { loggedIn = false; loading = false; bootstrapUnavailable = false; });
    } catch (_) {
      if (mounted) setState(() { loading = false; bootstrapUnavailable = true; });
    }
  }

  Future<void> _onLoggedIn() async {
    setState(() => loading = true);
    await _bootstrap();
  }

  /// An expired token is a normal event: the API layer has already cleared it,
  /// so the app returns to login instead of leaving the person on a screen
  /// that fails every action.
  void _onSessionExpired() {
    if (!mounted || !loggedIn) return;
    setState(() { loggedIn = false; role = 'customer'; loading = false; });
    final messenger = _messengerKey.currentState;
    messenger?.showSnackBar(
      const SnackBar(content: Text('Your session expired. Please sign in again.')),
    );
  }

  Future<void> _logout() async {
    await FirebaseGoogleSignIn.signOut();
    await GaonApi.logout();
    if (mounted) setState(() { loggedIn = false; role = 'customer'; loading = false; });
  }

  Widget _home() {
    if (bootstrapUnavailable) return Scaffold(body:Center(child:Padding(padding:const EdgeInsets.all(24),child:Column(mainAxisSize:MainAxisSize.min,children:[const Text('We could not confirm your account because the network or service is unavailable.',textAlign:TextAlign.center),const SizedBox(height:16),FilledButton(onPressed:(){setState(()=>loading=true);_bootstrap();},child:const Text('Retry'))]))));
    if (!loggedIn) return LoginScreen(onLoggedIn: _onLoggedIn);
    return switch (role) {
      'merchant' => MerchantWorkspace(onLogout: _logout),
      'delivery' => DeliveryWorkspace(onLogout: _logout),
      'admin' => AdminWorkspace(onLogout: _logout),
      _ => CustomerShell(onLogout: _logout),
    };
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      scaffoldMessengerKey: _messengerKey,
      debugShowCheckedModeBanner: false,
      title: 'GaonOne',
      theme: gaonTheme(),
      home: loading ? const Scaffold(body: Center(child: CircularProgressIndicator())) : _home(),
    );
  }
}
