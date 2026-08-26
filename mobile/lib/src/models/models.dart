class Village {
  final String id;
  final String name;
  final String district;
  final String state;
  Village({required this.id, required this.name, required this.district, required this.state});
  factory Village.fromJson(Map<String, dynamic> j) => Village(id: j['id'], name: j['name'], district: j['district'], state: j['state']);
}

class StoreModel {
  final String id;
  final String name;
  final String? description;
  final String? landmark;
  final bool deliveryEnabled;
  StoreModel({required this.id, required this.name, this.description, this.landmark, required this.deliveryEnabled});
  factory StoreModel.fromJson(Map<String, dynamic> j) => StoreModel(id: j['id'], name: j['name'], description: j['description'], landmark: j['landmark'], deliveryEnabled: j['delivery_enabled'] ?? false);
}

class StoreProduct {
  final String id;
  final String name;
  final String unit;
  final String price;
  final int stock;
  StoreProduct({required this.id, required this.name, required this.unit, required this.price, required this.stock});
  factory StoreProduct.fromJson(Map<String, dynamic> j) => StoreProduct(id: j['id'], name: j['product']['name'], unit: j['product']['unit'], price: j['price'].toString(), stock: j['stock_quantity'] ?? 0);
}
