import 'package:flutter/material.dart';

import '../api/gaon_api.dart';

class LoginScreen extends StatefulWidget {
  final VoidCallback onLoggedIn;

  const LoginScreen({super.key, required this.onLoggedIn});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final phoneController = TextEditingController(text: '+91');
  final nameController = TextEditingController();
  final otpController = TextEditingController();

  bool otpSent = false;
  bool loading = false;
  String? message;

  @override
  void dispose() {
    phoneController.dispose();
    nameController.dispose();
    otpController.dispose();
    super.dispose();
  }

  Future<void> requestOtp() async {
    setState(() {
      loading = true;
      message = null;
    });

    try {
      final code = await GaonApi.requestOtp(phoneController.text.trim());
      if (!mounted) return;
      setState(() {
        otpSent = true;
        message = code == null ? 'OTP sent' : 'Development OTP: $code';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => message = error.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> verifyOtp() async {
    setState(() {
      loading = true;
      message = null;
    });

    try {
      await GaonApi.verifyOtp(
        phoneController.text.trim(),
        otpController.text.trim(),
        nameController.text.trim(),
      );
      if (!mounted) return;
      widget.onLoggedIn();
    } catch (error) {
      if (!mounted) return;
      setState(() => message = error.toString());
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'GaonOne',
                        style: Theme.of(context).textTheme.headlineLarge?.copyWith(
                              fontWeight: FontWeight.w900,
                            ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Your village market, in your pocket.',
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                      const SizedBox(height: 28),
                      TextField(
                        controller: phoneController,
                        keyboardType: TextInputType.phone,
                        decoration: const InputDecoration(
                          labelText: 'Mobile number',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (!otpSent)
                        TextField(
                          controller: nameController,
                          decoration: const InputDecoration(
                            labelText: 'Name',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      if (otpSent)
                        TextField(
                          controller: otpController,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'OTP',
                            border: OutlineInputBorder(),
                          ),
                        ),
                      const SizedBox(height: 16),
                      FilledButton(
                        onPressed: loading
                            ? null
                            : (otpSent ? verifyOtp : requestOtp),
                        child: Text(
                          loading
                              ? 'Please wait...'
                              : otpSent
                                  ? 'Verify & continue'
                                  : 'Send OTP',
                        ),
                      ),
                      if (message != null) ...[
                        const SizedBox(height: 12),
                        Text(message!, textAlign: TextAlign.center),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
