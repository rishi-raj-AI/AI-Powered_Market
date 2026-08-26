import 'package:flutter/material.dart';
import '../api/gaon_api.dart';

class LoginScreen extends StatefulWidget {
  final VoidCallback onLoggedIn;
  const LoginScreen({super.key, required this.onLoggedIn});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final phone = TextEditingController(text: '+91');
  final name = TextEditingController();
  final otp = TextEditingController();
  bool otpSent = false;
  bool loading = false;
  String? message;
  Future<void> request() async {
    setState(() => loading = true);
    try {
      final code = await GaonApi.requestOtp(phone.text.trim());
      setState(() { otpSent = true; message = code == null ? 'OTP sent' : 'Development OTP: $code'; });
    } catch (e) { setState(() => message = e.toString()); }
    finally { setState(() => loading = false); }
  }
  Future<void> verify() async {
    setState(() => loading = true);
    try { await GaonApi.verifyOtp(phone.text.trim(), otp.text.trim(), name.text.trim()); widget.onLoggedIn(); }
    catch (e) { setState(() => message = e.toString()); }
    finally { setState(() => loading = false); }
  }
  @override
  Widget build(BuildContext context) => Scaffold(body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440), child: Card(child: Padding(padding: const EdgeInsets.all(24), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children:[Text('GaonOne', style: Theme.of(context).textTheme.headlineLarge?.copyWith(fontWeight: FontWeight.w900)),const SizedBox(height:8),Text('Your village market, in your pocket.',style:Theme.of(context).textTheme.bodyLarge),const SizedBox(height:28),TextField(controller:phone,keyboardType:TextInputType.phone,decoration:const InputDecoration(labelText:'Mobile number',border:OutlineInputBorder())),const SizedBox(height:12),if(!otpSent)TextField(controller:name,decoration:const InputDecoration(labelText:'Name',border:OutlineInputBorder())),if(otpSent)TextField(controller:otp,keyboardType:TextInputType.number,decoration:const InputDecoration(labelText:'OTP',border:OutlineInputBorder())),const SizedBox(height:16),FilledButton(onPressed:loading?null:(otpSent?verify:request),child:Text(loading?'Please wait...':otpSent?'Verify & continue':'Send OTP')),if(message!=null)...[const SizedBox(height:12),Text(message!,textAlign:TextAlign.center)] ])))))));
}
