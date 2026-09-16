import 'package:flutter/material.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';

class AccountScreen extends StatefulWidget {
  final VoidCallback onLogout;
  const AccountScreen({super.key,required this.onLogout});
  @override State<AccountScreen> createState()=>_AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen>{
  final business=TextEditingController(),gstin=TextEditingController(),name=TextEditingController();
  bool busy=false;UserModel? user;
  @override void initState(){super.initState();loadProfile();}
  @override void dispose(){business.dispose();gstin.dispose();name.dispose();super.dispose();}
  Future<void> loadProfile()async{try{final result=await GaonApi.me();if(mounted)setState((){user=result;name.text=result.fullName??'';});}catch(e){if(mounted)_message('$e');}}
  void _message(String text)=>ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(text)));
  Future<void> saveName()async{if(name.text.trim().isEmpty)return;setState(()=>busy=true);try{final result=await GaonApi.updateProfile(name.text.trim());if(mounted)setState(()=>user=result);if(mounted)_message('Name updated.');}catch(e){if(mounted)_message('$e');}finally{if(mounted)setState(()=>busy=false);}}
  Future<void> apply()async{if(business.text.trim().length<2)return;setState(()=>busy=true);try{await GaonApi.applyMerchant(business.text.trim(),gstin:gstin.text.trim().isEmpty?null:gstin.text.trim());if(!mounted)return;await showDialog(context:context,builder:(c)=>AlertDialog(title:const Text('Merchant application submitted'),content:const Text('Your account is now in merchant review. Sign in again to open the merchant workspace and track approval.'),actions:[FilledButton(onPressed:()=>Navigator.pop(c),child:const Text('Continue'))]));widget.onLogout();}catch(e){if(mounted)_message('$e');}finally{if(mounted)setState(()=>busy=false);}}
  @override Widget build(BuildContext c)=>ListView(padding:const EdgeInsets.all(16),children:[Text('Account',style:Theme.of(c).textTheme.headlineMedium?.copyWith(fontWeight:FontWeight.w800)),const SizedBox(height:12),Card(child:ListTile(leading:const Icon(Icons.verified_user_outlined),title:Text(user?.fullName??'Verified GaonOne account'),subtitle:Text(user?.phone??'Loading verified phone…'))),const SizedBox(height:16),TextField(controller:name,decoration:const InputDecoration(labelText:'Name'),textInputAction:TextInputAction.done,onSubmitted:busy?null:(_)=>saveName()),const SizedBox(height:10),FilledButton.tonal(onPressed:busy?null:saveName,child:Text(busy?'Saving…':'Save name')),const SizedBox(height:24),Text('Sell on GaonOne',style:Theme.of(c).textTheme.titleLarge?.copyWith(fontWeight:FontWeight.w700)),const Text('Apply as a local merchant. Admin approval is required before your storefront becomes public.'),const SizedBox(height:12),TextField(controller:business,decoration:const InputDecoration(labelText:'Business / shop name')),const SizedBox(height:10),TextField(controller:gstin,decoration:const InputDecoration(labelText:'GSTIN (optional)')),const SizedBox(height:10),FilledButton.icon(onPressed:busy?null:apply,icon:const Icon(Icons.storefront),label:Text(busy?'Submitting…':'Apply as merchant')),const SizedBox(height:28),OutlinedButton.icon(onPressed:widget.onLogout,icon:const Icon(Icons.logout),label:const Text('Log out'))]);
}
