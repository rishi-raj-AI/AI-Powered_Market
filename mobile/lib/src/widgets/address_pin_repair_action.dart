import 'package:flutter/material.dart';

import '../api/gaon_api.dart';
import '../models/models.dart';
import 'delivery_pin_picker.dart';

/// Repairs an old address without mutating the historical address/order row.
///
/// The API returns a NEW address ID; callers must refresh their address list
/// and never reuse the archived ID for a new quote or checkout.
class AddressPinRepairAction extends StatefulWidget {
  const AddressPinRepairAction({
    super.key,
    required this.address,
    required this.onReplaced,
    this.selectPin,
    this.confirmPin,
  });

  final AddressModel address;
  final Future<void> Function(AddressModel replacement) onReplaced;
  final Future<DeliveryPinCandidate?> Function(BuildContext context)? selectPin;
  final Future<AddressModel> Function(String addressId, DeliveryPinCandidate pin)?
      confirmPin;

  @override
  State<AddressPinRepairAction> createState() => _AddressPinRepairActionState();
}

class _AddressPinRepairActionState extends State<AddressPinRepairAction> {
  bool _busy = false;
  String? _error;

  Future<void> _repair() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final pin = await (widget.selectPin?.call(context) ??
          Navigator.of(context).push<DeliveryPinCandidate>(
            MaterialPageRoute(builder: (_) => const DeliveryPinPicker()),
          ));
      if (!mounted || pin == null) return;
      // The picker confirms a deliberate GPS/map selection; never turn a
      // searched-place centroid or the map's initial centre into a doorstep.
      if (!pin.isValid || !const {'gps', 'map_pin'}.contains(pin.source)) {
        throw const FormatException('Choose a valid GPS or manual map pin.');
      }
      final replacement = await (widget.confirmPin?.call(widget.address.id, pin) ??
          GaonApi.confirmAddressPin(
            widget.address.id,
            latitude: pin.latitude,
            longitude: pin.longitude,
            locationSource: pin.source,
            locationAccuracyMeters: pin.accuracyMeters,
          ));
      if (!mounted) return;
      await widget.onReplaced(replacement);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Delivery pin saved. Check delivery availability before ordering.')),
      );
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error is ApiException && error.statusCode == 404
            ? 'Address confirmation is unavailable. Refresh the app and try again.'
            : 'Could not save the pin. Your existing address is unchanged. ${error is ApiException ? error.message : ''}';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          TextButton.icon(
            onPressed: _busy ? null : _repair,
            icon: const Icon(Icons.edit_location_alt_outlined),
            label: const Text('Confirm saved address pin'),
          ),
          if (_busy) const LinearProgressIndicator(),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
        ],
      );
}
