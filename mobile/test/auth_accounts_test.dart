import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gaonone_mobile/main.dart';
import 'package:gaonone_mobile/src/api/gaon_api.dart';
import 'package:gaonone_mobile/src/screens/login_screen.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main(){
  setUp(()=>SharedPreferences.setMockInitialValues({}));

  testWidgets('direct OTP keeps the requested phone and supports change number',(tester)async{
    var requests=0;String? verifiedPhone;
    final client=MockClient((request)async{
      if(request.url.path.endsWith('/auth/request-otp')){requests++;return http.Response(jsonEncode({'message':'accepted','dev_otp':null,'expires_in_seconds':null,'resend_after_seconds':null,'request_limit':5,'request_window_seconds':900}),200);}
      if(request.url.path.endsWith('/auth/verify-otp')){verifiedPhone=jsonDecode(request.body)['phone'];return http.Response(jsonEncode({'access_token':'token','token_type':'bearer'}),200);}
      return http.Response('{}',404);
    });
    await http.runWithClient(()async{
      await tester.pumpWidget(MaterialApp(home:LoginScreen(onLoggedIn:(){})));
      await tester.enterText(find.widgetWithText(TextField,'Mobile number'),'9876543210');
      await tester.tap(find.text('Send OTP'));await tester.pumpAndSettle();
      expect(requests,1);expect(find.textContaining('controlled by the provider'),findsOneWidget);
      expect(tester.widget<TextField>(find.widgetWithText(TextField,'Mobile number')).enabled,isFalse);
      await tester.tap(find.text('Resend code'));await tester.pumpAndSettle();expect(requests,2);
      await tester.enterText(find.widgetWithText(TextField,'OTP'),'123456');
      await tester.tap(find.text('Verify & continue'));await tester.pumpAndSettle();
      expect(verifiedPhone,'9876543210');
      await tester.tap(find.text('Change number'));await tester.pumpAndSettle();
      expect(find.text('Send OTP'),findsOneWidget);
    },()=>client);
  });

  testWidgets('transient bootstrap failure preserves the stored session and offers retry',(tester)async{
    SharedPreferences.setMockInitialValues({'token':'preserve-me'});
    final client=MockClient((_)async=>throw const SocketException('offline'));
    await http.runWithClient(()async{await tester.pumpWidget(const GaonOneApp());await tester.pumpAndSettle();expect(find.text('Retry'),findsOneWidget);expect((await SharedPreferences.getInstance()).getString('token'),'preserve-me');},()=>client);
  });

  test('profile update sends only the allowed name field',()async{
    SharedPreferences.setMockInitialValues({'token':'token'});Map<String,dynamic>? payload;
    final client=MockClient((request)async{payload=jsonDecode(request.body);expect(request.method,'PATCH');expect(request.url.path,'/api/v1/users/me');return http.Response(jsonEncode({'id':'u1','phone':'+919876543210','full_name':'Asha Patil','role':'customer'}),200);});
    await http.runWithClient(()async{final user=await GaonApi.updateProfile('Asha Patil');expect(user.fullName,'Asha Patil');},()=>client);
    expect(payload,{'full_name':'Asha Patil'});
  });
}
