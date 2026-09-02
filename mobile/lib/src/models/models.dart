class UserModel {
  final String id;
  final String phone;
  final String? fullName;
  final String role;
  UserModel({required this.id, required this.phone, this.fullName, required this.role});
  factory UserModel.fromJson(Map<String, dynamic> j) => UserModel(id: j['id'], phone: j['phone'], fullName: j['full_name'], role: j['role']);
}

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
  final double? latitude;
  final double? longitude;
  final double? distanceKm;
  StoreModel({
    required this.id,
    required this.name,
    this.description,
    this.landmark,
    required this.deliveryEnabled,
    this.latitude,
    this.longitude,
    this.distanceKm,
  });
  factory StoreModel.fromJson(Map<String, dynamic> j) => StoreModel(
        id: j['id'],
        name: j['name'],
        description: j['description'],
        landmark: j['landmark'],
        deliveryEnabled: j['delivery_enabled'] ?? false,
        latitude: (j['latitude'] as num?)?.toDouble(),
        longitude: (j['longitude'] as num?)?.toDouble(),
        distanceKm: (j['distance_km'] as num?)?.toDouble(),
      );
}

class ProductModel {
  final String id;
  final String name;
  final String unit;
  ProductModel({required this.id, required this.name, required this.unit});
  factory ProductModel.fromJson(Map<String, dynamic> j) => ProductModel(id: j['id'], name: j['name'], unit: j['unit']);
}

class StoreProduct {
  final String id;
  final String productId;
  final String name;
  final String unit;
  final String price;
  final String? mrp;
  final int stock;
  final bool isAvailable;
  StoreProduct({required this.id, required this.productId, required this.name, required this.unit, required this.price, this.mrp, required this.stock, required this.isAvailable});
  factory StoreProduct.fromJson(Map<String, dynamic> j) => StoreProduct(
        id: j['id'],
        productId: j['product_id'],
        name: j['product']['name'],
        unit: j['product']['unit'],
        price: j['price'].toString(),
        mrp: j['mrp']?.toString(),
        stock: j['stock_quantity'] ?? 0,
        isAvailable: j['is_available'] ?? false,
      );
}

class CartItemModel {
  final String id;
  final int quantity;
  final StoreProduct product;
  CartItemModel({required this.id, required this.quantity, required this.product});
  factory CartItemModel.fromJson(Map<String, dynamic> j) => CartItemModel(id: j['id'], quantity: j['quantity'], product: StoreProduct.fromJson(j['store_product']));
}

class CartModel {
  final String id;
  final String? storeId;
  final List<CartItemModel> items;
  final String subtotal;
  CartModel({required this.id, this.storeId, required this.items, required this.subtotal});
  factory CartModel.fromJson(Map<String, dynamic> j) => CartModel(id: j['id'], storeId: j['store_id'], items: (j['items'] as List<dynamic>).map((e) => CartItemModel.fromJson(e)).toList(), subtotal: j['subtotal'].toString());
}

class AddressModel {
  final String id;
  final String villageId;
  final String label;
  final String landmark;
  final String? houseDetails;
  final double? latitude;
  final double? longitude;
  AddressModel({required this.id, required this.villageId, required this.label, required this.landmark, this.houseDetails, this.latitude, this.longitude});
  factory AddressModel.fromJson(Map<String, dynamic> j) => AddressModel(
        id: j['id'],
        villageId: j['village_id'],
        label: j['label'],
        landmark: j['landmark'],
        houseDetails: j['house_details'],
        latitude: (j['latitude'] as num?)?.toDouble(),
        longitude: (j['longitude'] as num?)?.toDouble(),
      );
}

class OrderModel {
  final String id;
  final String orderNumber;
  final String status;
  final String paymentMethod;
  final String paymentStatus;
  final String total;
  final String createdAt;
  OrderModel({required this.id, required this.orderNumber, required this.status, required this.paymentMethod, required this.paymentStatus, required this.total, required this.createdAt});
  factory OrderModel.fromJson(Map<String, dynamic> j) => OrderModel(id: j['id'], orderNumber: j['order_number'], status: j['status'], paymentMethod: j['payment_method'], paymentStatus: j['payment_status'], total: j['total'].toString(), createdAt: j['created_at']);
}

class DeliveryModel {
  final String id;
  final String orderId;
  final String status;
  DeliveryModel({required this.id, required this.orderId, required this.status});
  factory DeliveryModel.fromJson(Map<String, dynamic> j) => DeliveryModel(id: j['id'], orderId: j['order_id'], status: j['status']);
}

class DeliveryTaskModel {
  final String id;
  final String orderId;
  final String orderNumber;
  final String status;
  final String paymentMethod;
  final String paymentStatus;
  final String total;
  final String storeName;
  final String? storePhone;
  final String? storeLandmark;
  final double? storeLatitude;
  final double? storeLongitude;
  final String? recipientName;
  final String? recipientPhone;
  final String? houseDetails;
  final String customerLandmark;
  final String? customerDirections;
  final double? customerLatitude;
  final double? customerLongitude;
  DeliveryTaskModel({
    required this.id,
    required this.orderId,
    required this.orderNumber,
    required this.status,
    required this.paymentMethod,
    required this.paymentStatus,
    required this.total,
    required this.storeName,
    this.storePhone,
    this.storeLandmark,
    this.storeLatitude,
    this.storeLongitude,
    this.recipientName,
    this.recipientPhone,
    this.houseDetails,
    required this.customerLandmark,
    this.customerDirections,
    this.customerLatitude,
    this.customerLongitude,
  });
  factory DeliveryTaskModel.fromJson(Map<String, dynamic> j) => DeliveryTaskModel(
        id: j['id'],
        orderId: j['order_id'],
        orderNumber: j['order_number'],
        status: j['status'],
        paymentMethod: j['payment_method'],
        paymentStatus: j['payment_status'],
        total: j['total'].toString(),
        storeName: j['store_name'],
        storePhone: j['store_phone'],
        storeLandmark: j['store_landmark'],
        storeLatitude: (j['store_latitude'] as num?)?.toDouble(),
        storeLongitude: (j['store_longitude'] as num?)?.toDouble(),
        recipientName: j['recipient_name'],
        recipientPhone: j['recipient_phone'],
        houseDetails: j['house_details'],
        customerLandmark: j['customer_landmark'] ?? j['dropoff_area'] ?? 'Area disclosed after assignment',
        customerDirections: j['customer_directions'],
        customerLatitude: (j['customer_latitude'] as num?)?.toDouble(),
        customerLongitude: (j['customer_longitude'] as num?)?.toDouble(),
      );
}

class PaymentConfigModel {
  final bool enabled;
  final String provider;
  final String? keyId;
  PaymentConfigModel({required this.enabled, required this.provider, this.keyId});
  factory PaymentConfigModel.fromJson(Map<String, dynamic> j) => PaymentConfigModel(enabled: j['enabled'] ?? false, provider: j['provider'] ?? 'razorpay', keyId: j['key_id']);
}

class PaymentIntentModel {
  final String paymentAttemptId;
  final String providerOrderId;
  final int amountSubunits;
  final String currency;
  final String keyId;
  PaymentIntentModel({required this.paymentAttemptId, required this.providerOrderId, required this.amountSubunits, required this.currency, required this.keyId});
  factory PaymentIntentModel.fromJson(Map<String, dynamic> j) => PaymentIntentModel(
        paymentAttemptId: j['payment_attempt_id'],
        providerOrderId: j['provider_order_id'],
        amountSubunits: j['amount_subunits'],
        currency: j['currency'],
        keyId: j['key_id'],
      );
}

class NotificationEventModel {
  final String id;
  final String eventType;
  final String title;
  final String body;
  final String status;
  final String createdAt;
  NotificationEventModel({required this.id, required this.eventType, required this.title, required this.body, required this.status, required this.createdAt});
  factory NotificationEventModel.fromJson(Map<String, dynamic> j) => NotificationEventModel(
        id: j['id'],
        eventType: j['event_type'],
        title: j['title'],
        body: j['body'],
        status: j['status'],
        createdAt: j['created_at'],
      );
}
