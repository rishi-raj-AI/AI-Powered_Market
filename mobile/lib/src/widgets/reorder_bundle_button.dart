import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../api/gaon_api.dart';

class ReorderBundleButton extends StatefulWidget {
  final String orderId;
  const ReorderBundleButton({super.key, required this.orderId});
  @override State<ReorderBundleButton> createState()=>_ReorderBundleButtonState();
}
class _ReorderBundleButtonState extends State<ReorderBundleButton>{
  bool busy=false; Map<String,dynamic>? preview;
  Future<Map<String,String>> _headers() async {final p=await SharedPreferences.getInstance();final t=p.getString('token');return {'Content-Type':'application/json',if(t!=null)'Authorization':'Bearer $t'};}
  Future<void> run() async {setState(()=>busy=true);try{if(preview==null){final r=await http.get(Uri.parse('${GaonApi.baseUrl}/orders/${widget.orderId}/reorder-preview'),headers:await _headers()).timeout(GaonApi.timeout);if(r.statusCode<200||r.statusCode>=300)throw Exception('Could not preview this basket.');preview=Map<String,dynamic>.from(jsonDecode(r.body));}else{for(final raw in (preview!['items'] as List? ?? const [])){final item=Map<String,dynamic>.from(raw as Map);if(item['available']==true&&item['listing_id']!=null&&(item['available_quantity'] as num? ?? 0).toInt()>0){await GaonApi.addToCart('${item['listing_id']}',quantity:(item['available_quantity'] as num).toInt());}}if(mounted)ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('Available items added. Checkout will revalidate stock and pricing.')));}if(mounted)setState((){});}catch(e){if(mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text('$e'.replaceFirst('Exception: ',''))));}finally{if(mounted)setState(()=>busy=false);}}
  @override Widget build(BuildContext context)=>Column(crossAxisAlignment:CrossAxisAlignment.start,children:[OutlinedButton.icon(onPressed:busy?null:run,icon:const Icon(Icons.replay),label:Text(busy?'Checking…':preview==null?'Preview reorder':'Add available items')),if(preview!=null)Text('${preview!['available_items']} available • ${preview!['unavailable_items']} unavailable • est. ₹${preview!['estimated_subtotal']}',style:Theme.of(context).textTheme.bodySmall)]);
}
