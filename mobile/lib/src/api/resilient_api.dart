import '../models/models.dart';
import '../offline/offline_support.dart';
import 'gaon_api.dart';
import 'rider_api.dart';

class ResilientApi {
  static Map<String, dynamic> _village(Village v) => {'id': v.id, 'name': v.name, 'district': v.district, 'state': v.state};
  static Map<String, dynamic> _store(StoreModel s) => {
        'id': s.id,
        'name': s.name,
        'description': s.description,
        'landmark': s.landmark,
        'delivery_enabled': s.deliveryEnabled,
        'latitude': s.latitude,
        'longitude': s.longitude,
        'distance_km': s.distanceKm,
      };
  static Map<String, dynamic> _listing(StoreProduct p) => {
        'id': p.id,
        'product_id': p.productId,
        'price': p.price,
        'mrp': p.mrp,
        'stock_quantity': p.stock,
        'is_available': p.isAvailable,
        'product': {'id': p.productId, 'name': p.name, 'unit': p.unit},
      };
  static Map<String, dynamic> _order(OrderModel o) => {
        'id': o.id,
        'order_number': o.orderNumber,
        'status': o.status,
        'payment_method': o.paymentMethod,
        'payment_status': o.paymentStatus,
        'total': o.total,
        'created_at': o.createdAt,
      };
  static Map<String, dynamic> _task(DeliveryTaskModel t) => {
        'id': t.id,
        'order_id': t.orderId,
        'order_number': t.orderNumber,
        'status': t.status,
        'payment_method': t.paymentMethod,
        'payment_status': t.paymentStatus,
        'total': t.total,
        'store_name': t.storeName,
        'store_phone': t.storePhone,
        'store_landmark': t.storeLandmark,
        'store_latitude': t.storeLatitude,
        'store_longitude': t.storeLongitude,
        'recipient_name': t.recipientName,
        'recipient_phone': t.recipientPhone,
        'house_details': t.houseDetails,
        'customer_landmark': t.customerLandmark,
        'customer_directions': t.customerDirections,
        'customer_latitude': t.customerLatitude,
        'customer_longitude': t.customerLongitude,
      };

  static Future<CachedResult<List<Village>>> villages() => OfflineSupport.cached(
        key: 'villages',
        remote: GaonApi.villages,
        encode: (items) => items.map(_village).toList(),
        decode: (value) => (value as List).map((e) => Village.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<StoreModel>>> stores([String? villageId]) => OfflineSupport.cached(
        key: 'stores.${villageId ?? 'all'}',
        remote: () => GaonApi.stores(villageId),
        encode: (items) => items.map(_store).toList(),
        decode: (value) => (value as List).map((e) => StoreModel.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<StoreModel>>> nearbyStores(double lat, double lng, {double radiusKm = 15}) => OfflineSupport.cached(
        key: 'nearby.${lat.toStringAsFixed(2)}.${lng.toStringAsFixed(2)}.$radiusKm',
        remote: () => GaonApi.nearbyStores(lat, lng, radiusKm: radiusKm),
        encode: (items) => items.map(_store).toList(),
        decode: (value) => (value as List).map((e) => StoreModel.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<StoreProduct>>> storeProducts(String storeId) => OfflineSupport.cached(
        key: 'store-products.$storeId',
        remote: () => GaonApi.storeProducts(storeId),
        encode: (items) => items.map(_listing).toList(),
        decode: (value) => (value as List).map((e) => StoreProduct.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<OrderModel>>> orders() => OfflineSupport.cached(
        key: 'orders.customer',
        remote: GaonApi.orders,
        encode: (items) => items.map(_order).toList(),
        decode: (value) => (value as List).map((e) => OrderModel.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<OrderModel>>> merchantOrders() => OfflineSupport.cached(
        key: 'orders.merchant',
        remote: GaonApi.merchantOrders,
        encode: (items) => items.map(_order).toList(),
        decode: (value) => (value as List).map((e) => OrderModel.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<DeliveryTaskModel>>> availableTasks() => OfflineSupport.cached(
        key: 'delivery.available',
        remote: RiderApi.availableTasks,
        encode: (items) => items.map(_task).toList(),
        decode: (value) => (value as List).map((e) => DeliveryTaskModel.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );

  static Future<CachedResult<List<DeliveryTaskModel>>> myTasks() => OfflineSupport.cached(
        key: 'delivery.mine',
        remote: RiderApi.myTasks,
        encode: (items) => items.map(_task).toList(),
        decode: (value) => (value as List).map((e) => DeliveryTaskModel.fromJson(Map<String, dynamic>.from(e as Map))).toList(),
      );
}
