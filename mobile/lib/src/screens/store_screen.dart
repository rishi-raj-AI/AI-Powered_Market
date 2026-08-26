import 'package:flutter/material.dart';
import '../api/gaon_api.dart';
import '../models/models.dart';

class StoreScreen extends StatefulWidget { final StoreModel store; const StoreScreen({super.key,required this.store}); @override State<StoreScreen> createState()=>_StoreScreenState(); }
class _StoreScreenState extends State<StoreScreen>{List<StoreProduct> products=[];bool loading=true;@override void initState(){super.initState();load();}Future<void> load()async{final p=await GaonApi.storeProducts(widget.store.id);if(mounted)setState((){products=p;loading=false;});}@override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:Text(widget.store.name)),body:loading?const Center(child:CircularProgressIndicator()):ListView.separated(padding:const EdgeInsets.all(16),itemCount:products.length,separatorBuilder:(_,__)=>const SizedBox(height:8),itemBuilder:(context,i){final p=products[i];return Card(child:ListTile(title:Text(p.name,style:const TextStyle(fontWeight:FontWeight.w700)),subtitle:Text('${p.unit} • ${p.stock} in stock'),trailing:FilledButton(onPressed:p.stock<=0?null:()async{await GaonApi.addToCart(p.id);if(context.mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text('${p.name} added')));},child:Text('₹${p.price} +')));})));
}
