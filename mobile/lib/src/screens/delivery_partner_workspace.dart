import 'dart:async';

import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';

import '../api/resilient_api.dart';
import '../api/rider_api.dart';
import '../models/models.dart';
import '../offline/offline_support.dart';

class DeliveryPartnerWorkspace extends StatefulWidget {
  final VoidCallback onLogout;
  const DeliveryPartnerWorkspace({super.key, required this.onLogout});

  @override
  State<DeliveryPartnerWorkspace> createState() => _DeliveryPartnerWorkspaceState();
}

class _DeliveryPartnerWorkspaceState extends State<DeliveryPartnerWorkspace> {
  List<DeliveryTaskModel> available = [];
  List<DeliveryTaskModel> mine = [];
  bool loading = true;
  bool online = false;
  bool presenceBusy = false;
  bool cachedTasks = false;
  DateTime? cachedAt;
  String? error;
  String? locationMessage;
  StreamSubscription<Position>? locationStream;
  String? sharingDeliveryId;
  DateTime? lastSent;

  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    locationStream?.cancel();
    super.dispose();
  }

  Future<void> load() async {
    try {
      final availableResult = await ResilientApi.availableTasks();
      final mineResult = await ResilientApi.myTasks();
      Map<String, dynamic>? presence;
      try {
        presence = await RiderApi.presence();
      } catch (_) {
        presence = null;
      }
      if (!mounted) return;
      setState(() {
        available = availableResult.data;
        mine = mineResult.data;
        cachedTasks = availableResult.fromCache || mineResult.fromCache;
        cachedAt = mineResult.cachedAt ?? availableResult.cachedAt;
        if (presence != null) online = presence['is_online'] == true;
        loading = false;
        error = null;
      });
    } catch (e) {
      if (mounted) setState(() { loading = false; error = '$e'; });
    }
  }

  void snack(String message) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message.replaceFirst('Exception: ', ''))));
  }

  bool _requireLiveState() {
    if (!cachedTasks) return true;
    snack('Reconnect before changing delivery state. Saved tasks may be out of date.');
    return false;
  }

  Future<Position> _position() async {
    if (!await Geolocator.isLocationServiceEnabled()) throw Exception('Turn on location services first.');
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      throw Exception('Location permission is required for rider operations.');
    }
    return Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.high));
  }

  Future<void> setOnline(bool value) async {
    setState(() => presenceBusy = true);
    try {
      final position = await _position();
      final result = await RiderApi.updatePresence(latitude: position.latitude, longitude: position.longitude, isOnline: value);
      if (!mounted) return;
      final queued = result['queued_for_sync'] == true;
      setState(() {
        online = value;
        locationMessage = queued
            ? '${value ? 'Online' : 'Offline'} change saved locally • will sync when connection returns'
            : value
                ? 'Online • dispatch can see your fresh location'
                : 'Offline';
      });
      if (!value) await stopSharing();
      if (!queued) await load();
    } catch (e) {
      snack('$e');
    } finally {
      if (mounted) setState(() => presenceBusy = false);
    }
  }

  Future<void> claim(DeliveryTaskModel task) async {
    if (!_requireLiveState()) return;
    try { await RiderApi.claim(task.id); await load(); } catch (e) { snack('$e'); }
  }

  Future<void> pickup(DeliveryTaskModel task) async {
    if (!_requireLiveState()) return;
    try { await RiderApi.markPickedUp(task.id); await startSharing(task); await load(); } catch (e) { snack('$e'); }
  }

  Future<void> startSharing(DeliveryTaskModel task) async {
    if (!online) { snack('Go online before sharing live delivery location.'); return; }
    final position = await _position();
    final synced = await RiderApi.sendLocation(
      task.id,
      latitude: position.latitude,
      longitude: position.longitude,
      accuracy: position.accuracy,
      heading: position.heading >= 0 ? position.heading : null,
      speed: position.speed >= 0 ? position.speed : null,
      recordedAt: DateTime.now().toUtc(),
    );
    await locationStream?.cancel();
    sharingDeliveryId = task.id;
    lastSent = DateTime.now().toUtc();
    const settings = LocationSettings(accuracy: LocationAccuracy.high, distanceFilter: 8);
    locationStream = Geolocator.getPositionStream(locationSettings: settings).listen((position) async {
      final now = DateTime.now().toUtc();
      if (sharingDeliveryId != task.id || (lastSent != null && now.difference(lastSent!) < const Duration(seconds: 8))) return;
      lastSent = now;
      final uploaded = await RiderApi.sendLocation(
        task.id,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracy: position.accuracy,
        heading: position.heading >= 0 ? position.heading : null,
        speed: position.speed >= 0 ? position.speed : null,
        recordedAt: now,
      );
      if (mounted) {
        setState(() => locationMessage = uploaded
            ? 'Live GPS • accuracy ~${position.accuracy.round()} m'
            : 'GPS saved locally • latest point will sync after reconnect');
      }
    });
    if (mounted) setState(() => locationMessage = synced ? 'Live GPS started for ${task.orderNumber}' : 'GPS queued locally for ${task.orderNumber}');
  }

  Future<void> stopSharing() async {
    await locationStream?.cancel();
    locationStream = null;
    sharingDeliveryId = null;
    lastSent = null;
    if (mounted) setState(() {});
  }

  Future<void> reportFailure(DeliveryTaskModel task) async {
    if (!_requireLiveState()) return;
    String reason = 'customer_unavailable';
    final notes = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('Report delivery problem'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            DropdownButtonFormField<String>(
              initialValue: reason,
              items: const [
                DropdownMenuItem(value: 'customer_unavailable', child: Text('Customer unavailable')),
                DropdownMenuItem(value: 'address_not_found', child: Text('Address not found')),
                DropdownMenuItem(value: 'vehicle_issue', child: Text('Vehicle issue')),
                DropdownMenuItem(value: 'damaged_order', child: Text('Order damaged')),
                DropdownMenuItem(value: 'other', child: Text('Other')),
              ],
              onChanged: (value) => setDialogState(() => reason = value ?? reason),
            ),
            const SizedBox(height: 12),
            TextField(controller: notes, maxLines: 3, decoration: const InputDecoration(labelText: 'Notes')),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Report')),
          ],
        ),
      ),
    );
    if (ok == true) {
      try {
        await RiderApi.fail(task.id, reason: reason, notes: notes.text.trim().isEmpty ? null : notes.text.trim());
        if (sharingDeliveryId == task.id) await stopSharing();
        await load();
      } catch (e) { snack('$e'); }
    }
  }

  Future<void> completeWithOtp(DeliveryTaskModel task) async {
    if (!_requireLiveState()) return;
    try {
      final challenge = await RiderApi.issueProofChallenge(task.id);
      if (!mounted) return;
      final otp = TextEditingController();
      final recipient = TextEditingController(text: task.recipientName ?? '');
      final ok = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Verify delivery'),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('Ask the customer for the 6-digit code. Expires ${challenge['expires_at']}.'),
            const SizedBox(height: 12),
            TextField(controller: otp, keyboardType: TextInputType.number, maxLength: 6, decoration: const InputDecoration(labelText: 'Customer OTP')),
            TextField(controller: recipient, decoration: const InputDecoration(labelText: 'Recipient name')),
          ]),
          actions: [
            TextButton(onPressed: () => Navigator.pop(dialogContext, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(dialogContext, true), child: const Text('Verify & complete')),
          ],
        ),
      );
      if (ok == true) {
        if (otp.text.trim().length != 6) { snack('Enter the 6-digit OTP.'); return; }
        await RiderApi.verifyProof(task.id, otp: otp.text.trim(), recipientName: recipient.text.trim().isEmpty ? null : recipient.text.trim());
        await RiderApi.complete(task.id);
        if (sharingDeliveryId == task.id) await stopSharing();
        await load();
        snack('Delivery completed successfully.');
      }
    } catch (e) { snack('$e'); }
  }

  Widget taskCard(DeliveryTaskModel task, {required bool availableTask}) {
    final active = task.status == 'assigned' || task.status == 'picked_up';
    return Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [Expanded(child: Text(task.orderNumber, style: const TextStyle(fontWeight: FontWeight.w800))), Chip(label: Text(task.status.replaceAll('_', ' ')))]),
      Text(task.storeName, style: const TextStyle(fontWeight: FontWeight.w700)),
      Text('Pickup: ${task.storeLandmark ?? 'Store location'}'),
      Text('Drop: ${task.houseDetails ?? ''} ${task.customerLandmark}'),
      if (task.recipientName != null) Text('Customer: ${task.recipientName}${task.recipientPhone == null ? '' : ' • ${task.recipientPhone}'}'),
      Text('₹${task.total} • ${task.paymentMethod.toUpperCase()} • ${task.paymentStatus}'),
      const SizedBox(height: 10),
      Wrap(spacing: 8, runSpacing: 8, children: [
        if (availableTask) FilledButton.icon(onPressed: online && !cachedTasks ? () => claim(task) : null, icon: const Icon(Icons.task_alt), label: const Text('Claim')),
        if (!availableTask && task.status == 'assigned') FilledButton.icon(onPressed: cachedTasks ? null : () => pickup(task), icon: const Icon(Icons.inventory_2_outlined), label: const Text('Confirm pickup')),
        if (!availableTask && active && sharingDeliveryId != task.id) OutlinedButton.icon(onPressed: () => startSharing(task), icon: const Icon(Icons.location_on_outlined), label: const Text('Share GPS')),
        if (!availableTask && task.status == 'picked_up') FilledButton.icon(onPressed: cachedTasks ? null : () => completeWithOtp(task), icon: const Icon(Icons.verified_outlined), label: const Text('OTP & deliver')),
        if (!availableTask && active) TextButton.icon(onPressed: cachedTasks ? null : () => reportFailure(task), icon: const Icon(Icons.report_problem_outlined), label: const Text('Report issue')),
      ]),
    ])));
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    final activeMine = mine.where((task) => task.status == 'assigned' || task.status == 'picked_up').toList();
    final completed = mine.where((task) => task.status == 'delivered' || task.status == 'failed').toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Delivery partner'), actions: [IconButton(onPressed: widget.onLogout, icon: const Icon(Icons.logout))]),
      body: RefreshIndicator(
        onRefresh: load,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          if (cachedTasks) Card(child: ListTile(leading: const Icon(Icons.cloud_off_outlined), title: const Text('Showing saved delivery tasks'), subtitle: Text(cachedAt == null ? 'Reconnect before changing delivery state.' : 'Last synced ${cachedAt!.toLocal()}. Lifecycle actions are paused; GPS can still queue locally.'))),
          Card(child: SwitchListTile(
            title: Text(online ? 'You are online' : 'You are offline', style: const TextStyle(fontWeight: FontWeight.w800)),
            subtitle: Text(locationMessage ?? (online ? 'Eligible for nearby dispatch' : 'Go online to receive deliveries')),
            value: online,
            onChanged: presenceBusy ? null : setOnline,
            secondary: presenceBusy ? const CircularProgressIndicator() : Icon(online ? Icons.delivery_dining : Icons.offline_bolt_outlined),
          )),
          if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
          const SizedBox(height: 8),
          Text('Active delivery', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          if (activeMine.isEmpty) const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Text('No active delivery assigned.')),
          ...activeMine.map((task) => taskCard(task, availableTask: false)),
          const SizedBox(height: 12),
          Text('Available nearby tasks', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          if (!online) const Padding(padding: EdgeInsets.symmetric(vertical: 10), child: Text('Go online to claim available work.')),
          ...available.map((task) => taskCard(task, availableTask: true)),
          const SizedBox(height: 12),
          Text('Recent history', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
          ...completed.take(10).map((task) => taskCard(task, availableTask: false)),
        ]),
      ),
    );
  }
}
