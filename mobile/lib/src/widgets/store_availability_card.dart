import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../api/gaon_api.dart';

class StoreAvailabilityCard extends StatefulWidget {
  final String storeId;
  const StoreAvailabilityCard({super.key,required this.storeId});
  @override State<StoreAvailabilityCard> createState()=>_StoreAvailabilityCardState();
}
class _StoreAvailabilityCardState extends State<StoreAvailabilityCard>{Map<String,dynamic>? data;String? error;@override void initState(){super.initState();load();}Future<void> load()async{try{final r=await http.get(Uri.parse('${GaonApi.baseUrl}/stores/${widget.storeId}/availability')).timeout(GaonApi.timeout);if(r.statusCode<200||r.statusCode>=300)throw Exception('Live store hours unavailable');if(mounted)setState((){data=Map<String,dynamic>.from(jsonDecode(r.body));error=null;});}catch(e){if(mounted)setState(()=>error='$e'.replaceFirst('Exception: ',''));}}@override Widget build(BuildContext context){if(error!=null)return const Card(child:ListTile(leading:Icon(Icons.schedule_outlined),title:Text('Live store hours unavailable')));if(data==null)return const Card(child:ListTile(leading:Icon(Icons.schedule_outlined),title:Text('Checking live store availability…')));final open=data!['is_open']==true;final mins=data!['minutes_until_close'];final next=data!['next_open_at'];String detail;if(open&&mins!=null){detail='About $mins min until closing.';}else if(!open&&next!=null){final d=DateTime.parse('$next');detail='Next opening ${d.day}/${d.month} ${d.hour.toString().padLeft(2,'0')}:${d.minute.toString().padLeft(2,'0')} IST.';}else{detail='Store hours are not configured.';}if(data!['delivery_available']==true)detail+=' Delivery available now.';if(data!['pickup_available']==true)detail+=' Pickup available now.';return Card(child:ListTile(leading:Icon(open?Icons.storefront:Icons.store_mall_directory_outlined),title:Text(open?'Open now':'Closed now'),subtitle:Text(detail),trailing:IconButton(onPressed:load,icon:const Icon(Icons.refresh))));}}
